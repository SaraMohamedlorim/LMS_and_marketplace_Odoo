from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

class LMSSecurity(models.AbstractModel):
    _name = 'lms.security'
    _description = 'LMS Security Helper Functions'
    
    @api.model
    def check_student_access(self, record_id, model_name):
        """Check if current user has student access to record"""
        user = self.env.user
        if user.has_group('lms.group_lms_administrator') or user.has_group('lms.group_lms_manager'):
            return True
        
        if user.has_group('lms.group_lms_student'):
            # Check if record belongs to student
            if model_name == 'lms.enrollment':
                enrollment = self.env[model_name].browse(record_id)
                return enrollment.student_id == user.partner_id
            elif model_name == 'lms.certificate':
                certificate = self.env[model_name].browse(record_id)
                return certificate.student_id == user.partner_id
            elif model_name == 'lms.content.progress':
                progress = self.env[model_name].browse(record_id)
                return progress.student_id == user.partner_id
        
        return False
    
    @api.model
    def check_instructor_access(self, record_id, model_name):
        """Check if current user has instructor access to record"""
        user = self.env.user
        if user.has_group('lms.group_lms_administrator') or user.has_group('lms.group_lms_manager'):
            return True
        
        if user.has_group('lms.group_lms_instructor'):
            partner_id = user.partner_id.id
            
            if model_name == 'lms.course':
                course = self.env[model_name].browse(record_id)
                return course.instructor_id.id == partner_id
            elif model_name == 'lms.enrollment':
                enrollment = self.env[model_name].browse(record_id)
                return enrollment.course_id.instructor_id.id == partner_id
            elif model_name == 'lms.live.session':
                session = self.env[model_name].browse(record_id)
                return session.instructor_id.id == partner_id
        
        return False
    
    @api.model
    def check_corporate_access(self, company_id):
        """Check if user has access to corporate data"""
        user = self.env.user
        if user.has_group('lms.group_lms_administrator') or user.has_group('lms.group_lms_manager'):
            return True
        
        if user.has_group('group_hr_manager'):
            return user.company_id.id == company_id
        
        return False
    
    @api.model
    def filter_student_records(self, records, model_name):
        """Filter records for student view"""
        user = self.env.user
        
        if user.has_group('lms.group_lms_administrator') or user.has_group('lms.group_lms_manager'):
            return records
        
        if user.has_group('lms.group_lms_student'):
            partner_id = user.partner_id.id
            
            if model_name == 'lms.enrollment':
                return records.filtered(lambda r: r.student_id.id == partner_id)
            elif model_name == 'lms.certificate':
                return records.filtered(lambda r: r.student_id.id == partner_id)
            elif model_name == 'lms.content.progress':
                return records.filtered(lambda r: r.student_id.id == partner_id)
        
        return self.env[model_name]
    
    @api.model
    def filter_instructor_records(self, records, model_name):
        """Filter records for instructor view"""
        user = self.env.user
        
        if user.has_group('lms.group_lms_administrator') or user.has_group('lms.group_lms_manager'):
            return records
        
        if user.has_group('lms.group_lms_instructor'):
            partner_id = user.partner_id.id
            
            if model_name == 'lms.course':
                return records.filtered(lambda r: r.instructor_id.id == partner_id)
            elif model_name == 'lms.enrollment':
                return records.filtered(lambda r: r.course_id.instructor_id.id == partner_id)
            elif model_name == 'lms.live.session':
                return records.filtered(lambda r: r.instructor_id.id == partner_id)
        
        return self.env[model_name]