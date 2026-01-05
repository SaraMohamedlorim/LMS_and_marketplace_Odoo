from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # الحقول الخاصة بـ LMS
    is_learner = fields.Boolean(
        string='Is Learner',
        default=False,
        help='Check if this partner is a learner/student'
    )
    
    is_instructor = fields.Boolean(
        string='Is Instructor',
        default=False,
        help='Check if this partner is an instructor'
    )
    
    lms_points = fields.Integer(
        string='Learning Points',
        default=0,
        help='Total points earned from achievements'
    )
    
    lms_level = fields.Integer(
        string='Learning Level',
        default=1,
        help='Learning level based on accumulated points'
    )
    
    # التاريخ الأخير للتعلم
    last_learning_date = fields.Datetime(
        string='Last Learning Activity',
        help='Date of last learning activity'
    )
    
    # الإنجازات
    achievement_ids = fields.One2many(
        'lms.achievement',
        'student_id',
        string='Achievements'
    )
    
    # التسجيلات
    enrollment_ids = fields.One2many(
        'lms.enrollment',
        'student_id',
        string='Course Enrollments'
    )
    
    # الشهادات
    certificate_ids = fields.One2many(
        'lms.certificate',
        'student_id',
        string='Certificates'
    )



    def action_mark_as_learner(self):
        """Mark partner as learner"""
        for partner in self:
            partner.write({
                'is_learner': True,
                'last_learning_date': fields.Datetime.now()
            })
        return True
    
    def action_mark_as_instructor(self):
        """Mark partner as instructor"""
        for partner in self:
            partner.write({
                'is_instructor': True
            })
        return True
    
    def action_view_lms_points(self):
        """View LMS points details"""
        # يمكنك إرجاع action أو تنفيذ منطق معين
        return {
            'type': 'ir.actions.act_window',
            'name': 'LMS Points Details',
            'res_model': 'res.partner',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }