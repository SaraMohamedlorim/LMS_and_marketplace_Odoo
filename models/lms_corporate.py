from odoo import models, fields, api
from odoo.exceptions import UserError

class LMSCorporate(models.Model):
    _name = 'lms.corporate'
    _description = 'LMS Corporate Management'
    
    @api.model
    def create_corporate_account(self, company_id, admin_user_id):
        """Create corporate account with bulk enrollment capabilities"""
        company = self.env['res.company'].browse(company_id)
        admin_user = self.env['res.users'].browse(admin_user_id)
        
        # Create corporate group
        corporate_group = self.env['res.groups'].create({
            'name': f'Corporate - {company.name}',
            'category_id': self.env.ref('base.module_category_hr').id,
        })
        
        # Configure corporate settings
        corporate_settings = {
            'company_id': company_id,
            'admin_user_id': admin_user_id,
            'corporate_group_id': corporate_group.id,
            'auto_enrollment': True,
            'custom_certificate': False,
            'reporting_access': True,
        }
        
        return corporate_settings
    
    @api.model
    def bulk_enroll_employees(self, company_id, course_ids, employee_ids=None):
        """Bulk enroll employees in courses"""
        company = self.env['res.company'].browse(company_id)
        
        if not employee_ids:
            # Get all employees of the company
            employees = self.env['hr.employee'].search([
                ('company_id', '=', company_id)
            ])
            employee_ids = employees.mapped('user_id.partner_id').ids
        else:
            employees = self.env['hr.employee'].browse(employee_ids)
            employee_ids = employees.mapped('user_id.partner_id').ids
        
        courses = self.env['lms.course'].browse(course_ids)
        
        enrollments = []
        for course in courses:
            for employee_id in employee_ids:
                # Check if already enrolled
                existing = self.env['lms.enrollment'].search([
                    ('course_id', '=', course.id),
                    ('student_id', '=', employee_id)
                ])
                
                if not existing:
                    enrollment = self.env['lms.enrollment'].create({
                        'student_id': employee_id,
                        'course_id': course.id,
                        'company_id': company_id,
                        'is_corporate_enrollment': True,
                        'payment_status': 'free',  # Corporate accounts typically have pre-paid access
                        'state': 'in_progress',
                    })
                    enrollments.append(enrollment.id)
        
        return enrollments
    
    @api.model
    def generate_training_report(self, company_id, date_from=None, date_to=None):
        """Generate comprehensive training report for corporation"""
        company = self.env['res.company'].browse(company_id)
        
        # Get all corporate enrollments
        domain = [('company_id', '=', company_id)]
        if date_from:
            domain.append(('enrollment_date', '>=', date_from))
        if date_to:
            domain.append(('enrollment_date', '<=', date_to))
        
        enrollments = self.env['lms.enrollment'].search(domain)
        employees = self.env['hr.employee'].search([('company_id', '=', company_id)])
        
        report_data = {
            'company_name': company.name,
            'report_period': f"{date_from} to {date_to}" if date_from and date_to else "All Time",
            'total_employees': len(employees),
            'enrolled_employees': len(set(enrollments.mapped('student_id'))),
            'total_enrollments': len(enrollments),
            'completion_statistics': {
                'completed': len(enrollments.filtered(lambda e: e.state == 'completed')),
                'in_progress': len(enrollments.filtered(lambda e: e.state == 'in_progress')),
                'not_started': len(enrollments.filtered(lambda e: e.state == 'draft')),
            },
            'course_performance': {},
            'department_breakdown': {},
            'skill_coverage': {},
        }
        
        # Course performance
        for course in enrollments.mapped('course_id'):
            course_enrollments = enrollments.filtered(lambda e: e.course_id == course)
            completed = course_enrollments.filtered(lambda e: e.state == 'completed')
            
            report_data['course_performance'][course.name] = {
                'total_enrollments': len(course_enrollments),
                'completed': len(completed),
                'completion_rate': (len(completed) / len(course_enrollments)) * 100 if course_enrollments else 0,
                'average_score': sum(completed.mapped('score')) / len(completed) if completed else 0,
            }
        
        # Department breakdown
        for employee in employees:
            dept = employee.department_id.name if employee.department_id else 'No Department'
            if dept not in report_data['department_breakdown']:
                report_data['department_breakdown'][dept] = {
                    'total_employees': 0,
                    'enrolled_employees': 0,
                    'completed_courses': 0,
                }
            
            report_data['department_breakdown'][dept]['total_employees'] += 1
            
            employee_enrollments = enrollments.filtered(
                lambda e: e.student_id == employee.user_id.partner_id
            )
            if employee_enrollments:
                report_data['department_breakdown'][dept]['enrolled_employees'] += 1
                report_data['department_breakdown'][dept]['completed_courses'] += len(
                    employee_enrollments.filtered(lambda e: e.state == 'completed')
                )
        
        return report_data
    
    @api.model
    def sync_hr_employees(self, company_id):
        """Sync HR employees with LMS students"""
        company = self.env['res.company'].browse(company_id)
        employees = self.env['hr.employee'].search([('company_id', '=', company_id)])
        
        created_count = 0
        updated_count = 0
        
        for employee in employees:
            if employee.user_id:
                partner = employee.user_id.partner_id
                # Ensure partner is marked as learner
                if not partner.is_learner:
                    partner.write({'is_learner': True})
                    updated_count += 1
            else:
                # Create user account for employee
                user_vals = {
                    'name': employee.name,
                    'login': employee.work_email or f"{employee.name.replace(' ', '.').lower()}@company.com",
                    'company_id': company_id,
                    'company_ids': [(6, 0, [company_id])],
                }
                user = self.env['res.users'].create(user_vals)
                employee.write({'user_id': user.id})
                
                # Mark partner as learner
                user.partner_id.write({'is_learner': True})
                created_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'total_employees': len(employees),
        }

class LMSComplianceTracking(models.Model):
    _name = 'lms.compliance.tracking'
    _description = 'LMS Compliance and Certification Tracking'
    
    @api.model
    def track_compliance(self, company_id, compliance_rule_id):
        """Track compliance with training requirements"""
        company = self.env['res.company'].browse(company_id)
        compliance_rule = self.env['lms.compliance.rule'].browse(compliance_rule_id)
        
        employees = self.env['hr.employee'].search([('company_id', '=', company_id)])
        
        compliance_report = {
            'rule_name': compliance_rule.name,
            'required_course': compliance_rule.course_id.name,
            'compliance_deadline': compliance_rule.deadline_date,
            'employees': [],
        }
        
        for employee in employees:
            # Check if employee has completed required course
            enrollment = self.env['lms.enrollment'].search([
                ('student_id', '=', employee.user_id.partner_id.id),
                ('course_id', '=', compliance_rule.course_id.id),
                ('state', '=', 'completed'),
            ], limit=1)
            
            employee_status = {
                'employee_name': employee.name,
                'department': employee.department_id.name if employee.department_id else 'N/A',
                'is_compliant': bool(enrollment),
                'completion_date': enrollment.completion_date if enrollment else None,
                'days_until_deadline': None,
            }
            
            if compliance_rule.deadline_date and not employee_status['is_compliant']:
                deadline = fields.Datetime.from_string(compliance_rule.deadline_date)
                today = fields.Datetime.now()
                employee_status['days_until_deadline'] = (deadline - today).days
            
            compliance_report['employees'].append(employee_status)
        
        return compliance_report
    
    @api.model
    def send_compliance_reminders(self, company_id, compliance_rule_id):
        """Send reminders for compliance deadlines"""
        compliance_report = self.track_compliance(company_id, compliance_rule_id)
        
        for employee_status in compliance_report['employees']:
            if not employee_status['is_compliant']:
                days_until_deadline = employee_status['days_until_deadline']
                
                if days_until_deadline and days_until_deadline <= 30:
                    # Send reminder email
                    self._send_reminder_email(employee_status, compliance_report)
        
        return len([e for e in compliance_report['employees'] if not e['is_compliant']])
    
    def _send_reminder_email(self, employee_status, compliance_report):
        """Send compliance reminder email"""
        # Implementation for sending email reminders
        template = self.env.ref('lms_marketplace.compliance_reminder_email')
        
        template.with_context({
            'employee': employee_status,
            'compliance_rule': compliance_report,
        }).send_mail(self.id, force_send=True)