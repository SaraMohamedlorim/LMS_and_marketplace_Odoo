from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LMSEnrollment(models.Model):
    _name = 'lms.enrollment'
    _description = 'LMS Course Enrollment'
    _rec_name = 'display_name'
    _order = 'enrollment_date desc'

    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    
    student_id = fields.Many2one(
        'res.partner', 
        string='Student', 
        required=True,
        domain=[('is_learner', '=', True)]
    )
    course_id = fields.Many2one(
        'lms.course', 
        string='Course', 
        required=True
    )

    instructor_id = fields.Many2one(
        'res.partner', 
        string='Instructor', 
        domain=[('is_instructor', '=', True)],
        required=True,
        tracking=True
    )
    
    enrollment_date = fields.Datetime(
        string='Enrollment Date', 
        default=fields.Datetime.now
    )
    completion_date = fields.Datetime(string='Completion Date')

    compliance_rule_id = fields.Many2one(
        'lms.compliance.rule',
        string='Compliance Rule',
        help='If this enrollment is required by a compliance rule'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    progress = fields.Float(string='Progress (%)', compute='_compute_progress')
    score = fields.Float(string='Overall Score (%)')
    
    # Payment information
    payment_status = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('free', 'Free'),
        ('refunded', 'Refunded'),
    ], string='Payment Status', default='pending')
    
    invoice_id = fields.Many2one('account.move', string='Invoice')
    payment_id = fields.Many2one('account.payment', string='Payment')
    
    # Content tracking
    content_progress_ids = fields.One2many(
        'lms.content.progress', 
        'enrollment_id', 
        string='Content Progress'
    )
    
    # Certificate
    certificate_id = fields.Many2one('lms.certificate', string='Certificate')
    
    # Corporate enrollment
    is_corporate_enrollment = fields.Boolean(string='Corporate Enrollment')
    company_id = fields.Many2one('res.company', string='Company')
    manager_id = fields.Many2one('res.partner', string='Manager')
    
    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for enrollment in self:
            enrollment.display_name = f"{enrollment.student_id.name} - {enrollment.course_id.name}"
    
    @api.depends('content_progress_ids', 'course_id')
    def _compute_progress(self):
        for enrollment in self:
            if not enrollment.course_id or not enrollment.course_id.modules:
                enrollment.progress = 0
                continue
            
            total_contents = sum(
                len(module.contents) for module in enrollment.course_id.modules
            )
            
            if total_contents == 0:
                enrollment.progress = 0
                continue
            
            completed_contents = len(enrollment.content_progress_ids.filtered(
                lambda cp: cp.state == 'completed'
            ))
            
            enrollment.progress = (completed_contents / total_contents) * 100
    
    def action_start_course(self):
        self.write({'state': 'in_progress'})
    
    def action_complete_course(self):
        if self.progress < 100:
            raise UserError(_("Cannot complete course with progress less than 100%"))
        
        certificate = self.env['lms.certificate'].create({
            'student_id': self.student_id.id,
            'course_id': self.course_id.id,
            'enrollment_id': self.id,
            'issue_date': fields.Datetime.now(),
        })
        
        self.write({
            'state': 'completed',
            'completion_date': fields.Datetime.now(),
            'certificate_id': certificate.id,
        })
    
    def action_cancel_enrollment(self):
        self.write({'state': 'cancelled'})
    
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'completed':
            return self.env.ref('lms_marketplace.mt_enrollment_completed')
        return super()._track_subtype(init_values)

class LMSContentProgress(models.Model):
    _name = 'lms.content.progress'
    _description = 'LMS Content Progress Tracking'
    
    enrollment_id = fields.Many2one(
        'lms.enrollment', 
        string='Enrollment', 
        required=True,
        ondelete='cascade'
    )
    content_id = fields.Many2one('lms.content', string='Content', required=True)
    module_id = fields.Many2one(
        'lms.module', 
        string='Module', 
        related='content_id.module_id',
        store=True
    )
    
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='not_started')
    
    start_date = fields.Datetime(string='Start Date')
    completion_date = fields.Datetime(string='Completion Date')
    time_spent = fields.Float(string='Time Spent (minutes)')
    
    quiz_attempt_id = fields.Many2one('lms.quiz.attempt', string='Quiz Attempt')
    score = fields.Float(string='Score', related='quiz_attempt_id.score')
    
    @api.model
    def create(self, vals):
        if 'state' in vals and vals['state'] == 'in_progress' and not vals.get('start_date'):
            vals['start_date'] = fields.Datetime.now()
        return super().create(vals)
    
    def write(self, vals):
        if 'state' in vals and vals['state'] == 'completed':
            vals['completion_date'] = fields.Datetime.now()
        return super().write(vals)