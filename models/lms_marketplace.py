from odoo import models, fields, api
from odoo.exceptions import UserError

class LMSMarketplaceSettings(models.TransientModel):
    _name = 'lms.marketplace.settings'
    _inherit = 'res.config.settings'
    _description = 'LMS Marketplace Settings'
    
    revenue_share_percentage = fields.Float(
        string='Platform Revenue Share (%)',
        default=30.0,
        config_parameter='lms_marketplace.revenue_share_percentage'
    )
    
    instructor_payout_delay = fields.Integer(
        string='Payout Delay (days)',
        default=30,
        config_parameter='lms_marketplace.instructor_payout_delay'
    )
    
    allow_instructor_registration = fields.Boolean(
        string='Allow Instructor Registration',
        default=True,
        config_parameter='lms_marketplace.allow_instructor_registration'
    )
    
    minimum_payout_amount = fields.Float(
        string='Minimum Payout Amount',
        default=50.0,
        config_parameter='lms_marketplace.minimum_payout_amount'
    )
    
    automatic_payouts = fields.Boolean(
        string='Automatic Payouts',
        default=False,
        config_parameter='lms_marketplace.automatic_payouts'
    )

class LMSInstructor(models.Model):
    _name = 'lms.instructor'
    _description = 'LMS Instructor'
    _inherits = {'res.partner': 'partner_id'}
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    
    bio = fields.Html(string='Biography')
    expertise = fields.Many2many('lms.tag', string='Areas of Expertise')
    
    total_courses = fields.Integer(
        string='Total Courses',
        compute='_compute_course_stats'
    )
    total_students = fields.Integer(
        string='Total Students',
        compute='_compute_course_stats'
    )
    average_rating = fields.Float(
        string='Average Rating',
        compute='_compute_course_stats'
    )
    
    courses = fields.One2many('lms.course', 'instructor_id', string='Courses')
    
    payout_method = fields.Selection([
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('stripe', 'Stripe'),
    ], string='Payout Method')
    
    payout_email = fields.Char(string='Payout Email')
    bank_account = fields.Char(string='Bank Account')
    
    total_earnings = fields.Float(string='Total Earnings', compute='_compute_earnings')
    available_balance = fields.Float(string='Available Balance', compute='_compute_earnings')
    pending_balance = fields.Float(string='Pending Balance', compute='_compute_earnings')
    
    is_verified = fields.Boolean(string='Verified Instructor')
    
    @api.depends('courses', 'courses.enrollments')
    def _compute_course_stats(self):
        for instructor in self:
            published_courses = instructor.courses.filtered(lambda c: c.published)
            instructor.total_courses = len(published_courses)
            
            total_students = 0
            total_rating = 0
            rating_count = 0
            
            for course in published_courses:
                total_students += course.current_students
                if course.rating_avg:
                    total_rating += course.rating_avg
                    rating_count += 1
            
            instructor.total_students = total_students
            instructor.average_rating = total_rating / rating_count if rating_count > 0 else 0
    
    @api.depends('courses.enrollments.payment_status')
    def _compute_earnings(self):
        for instructor in self:

            enrollments = self.env['lms.enrollment'].search([
                ('instructor_id', '=', instructor.id),
                ('payment_status', '=', 'paid')
            ])
            
            total_earnings = sum(enrollment.course_id.price for enrollment in enrollments)
            revenue_share = self.env['ir.config_parameter'].sudo().get_param(
                'lms_marketplace.revenue_share_percentage', 30.0
            )
            
            instructor_share = (100 - float(revenue_share)) / 100
            instructor.total_earnings = total_earnings * instructor_share
            
            # Simplified calculation - in reality, you'd track payouts
            instructor.available_balance = instructor.total_earnings
            instructor.pending_balance = 0
    
    def action_request_payout(self):
        if self.available_balance < float(self.env['ir.config_parameter'].sudo().get_param(
            'lms_marketplace.minimum_payout_amount', 50.0
        )):
            raise UserError(_("Minimum payout amount not reached."))
        
        # Create payout record
        payout = self.env['lms.payout'].create({
            'instructor_id': self.id,
            'amount': self.available_balance,
            'payout_method': self.payout_method,
            'status': 'requested',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lms.payout',
            'res_id': payout.id,
            'view_mode': 'form',
            'target': 'current',
        }

class LMSPayout(models.Model):
    _name = 'lms.payout'
    _description = 'LMS Instructor Payout'
    
    instructor_id = fields.Many2one('lms.instructor', string='Instructor', required=True)
    amount = fields.Float(string='Amount', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    payout_method = fields.Selection([
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('stripe', 'Stripe'),
    ], string='Payout Method', required=True)
    
    status = fields.Selection([
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], string='Status', default='requested')
    
    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now)
    process_date = fields.Datetime(string='Process Date')
    complete_date = fields.Datetime(string='Complete Date')
    
    transaction_id = fields.Char(string='Transaction ID')
    notes = fields.Text(string='Notes')