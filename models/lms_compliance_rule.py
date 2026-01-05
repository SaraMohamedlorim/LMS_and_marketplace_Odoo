from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

class LmsComplianceRule(models.Model):
    _name = 'lms.compliance.rule'
    _description = 'LMS Compliance and Training Rule'
    _order = 'priority desc, deadline_date asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Rule Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    code = fields.Char(
        string='Rule Code',
        default=lambda self: self._generate_rule_code(),
        readonly=True
    )
    
    # Rule Scope
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        tracking=True
    )
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help='Leave empty to apply to all departments'
    )
    job_position_ids = fields.Many2many(
        'hr.job',
        string='Job Positions',
        help='Leave empty to apply to all positions'
    )
    employee_category_ids = fields.Many2many(
        'hr.employee.category',
        string='Employee Categories'
    )
    
    # Training Requirements
    course_id = fields.Many2one(
        'lms.course',
        string='Required Course',
        required=True,
        tracking=True
    )
    alternative_course_ids = fields.Many2many(
        'lms.course',
        'compliance_rule_alternative_course_rel',
        'rule_id',
        'course_id',
        string='Alternative Courses'
    )
    
    # Completion Requirements
    min_score = fields.Float(
        string='Minimum Passing Score (%)',
        default=70.0,
        help='Minimum score required on course assessment'
    )
    require_certificate = fields.Boolean(
        string='Require Certificate',
        default=True,
        help='Certificate must be issued to count as compliant'
    )
    
    # Deadlines and Renewals
    deadline_date = fields.Date(
        string='Deadline Date',
        required=True,
        tracking=True
    )
    days_before_deadline_reminder = fields.Integer(
        string='Reminder Days Before Deadline',
        default=30,
        help='Send reminder this many days before deadline'
    )
    
    renewal_required = fields.Boolean(string='Requires Renewal', default=False)
    renewal_period_months = fields.Integer(
        string='Renewal Period (months)',
        default=12,
        help='Certificate validity period in months'
    )
    
    # Enforcement
    priority = fields.Selection([
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('critical', 'Critical'),
    ], string='Priority', default='medium', tracking=True)
    
    enforcement_action = fields.Selection([
        ('warning', 'Warning Only'),
        ('restrict_access', 'Restrict System Access'),
        ('report_manager', 'Report to Manager'),
        ('hr_action', 'HR Disciplinary Action'),
    ], string='Enforcement Action', default='warning')
    
    # Status
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    effective_date = fields.Date(string='Effective Date', default=fields.Date.today)
    end_date = fields.Date(string='End Date')
    
    # Statistics
    total_affected_employees = fields.Integer(
        string='Affected Employees',
        compute='_compute_compliance_stats'
    )
    compliant_employees = fields.Integer(
        string='Compliant Employees',
        compute='_compute_compliance_stats'
    )
    non_compliant_employees = fields.Integer(
        string='Non-Compliant Employees',
        compute='_compute_compliance_stats'
    )
    compliance_rate = fields.Float(
        string='Compliance Rate (%)',
        compute='_compute_compliance_stats'
    )
    
    # Tracking
    last_compliance_check = fields.Datetime(string='Last Compliance Check')
    next_check_date = fields.Date(string='Next Check Date')
    
    # Related Records
    enrollment_ids = fields.One2many(
        'lms.enrollment',
        'compliance_rule_id',
        string='Related Enrollments'
    )
    exception_ids = fields.One2many(
        'lms.compliance.exception',
        'rule_id',
        string='Exceptions'
    )
    reminder_log_ids = fields.One2many(
        'lms.compliance.reminder.log',
        'rule_id',
        string='Reminder Logs'
    )
    
    def _generate_rule_code(self):
        """Generate unique rule code"""
        prefix = 'COMP'
        sequence = self.env['ir.sequence'].next_by_code('lms.compliance.rule')
        return f"{prefix}-{sequence}"
    
    @api.depends('company_id', 'department_ids', 'job_position_ids')
    def _compute_compliance_stats(self):
        for rule in self:
            affected_employees = rule._get_affected_employees()
            rule.total_affected_employees = len(affected_employees)
            
            compliant_count = 0
            for employee in affected_employees:
                if rule._check_employee_compliance(employee.id):
                    compliant_count += 1
            
            rule.compliant_employees = compliant_count
            rule.non_compliant_employees = rule.total_affected_employees - compliant_count
            
            if rule.total_affected_employees > 0:
                rule.compliance_rate = (compliant_count / rule.total_affected_employees) * 100
            else:
                rule.compliance_rate = 0
    
    def _get_affected_employees(self):
        """Get employees affected by this compliance rule"""
        domain = [('company_id', '=', self.company_id.id)]
        
        # Filter by department if specified
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        
        # Filter by job position if specified
        if self.job_position_ids:
            domain.append(('job_id', 'in', self.job_position_ids.ids))
        
        # Filter by employee category if specified
        if self.employee_category_ids:
            domain.append(('category_ids', 'in', self.employee_category_ids.ids))
        
        employees = self.env['hr.employee'].search(domain)
        return employees
    
    def _check_employee_compliance(self, employee_id):
        """Check if an employee is compliant with this rule"""
        employee = self.env['hr.employee'].browse(employee_id)
        partner = employee.user_id.partner_id
        
        if not partner:
            return False
        
        # Check for completed enrollment in required course or alternatives
        required_courses = [self.course_id.id] + self.alternative_course_ids.ids
        
        enrollments = self.env['lms.enrollment'].search([
            ('student_id', '=', partner.id),
            ('course_id', 'in', required_courses),
            ('state', '=', 'completed'),
        ])
        
        for enrollment in enrollments:
            # Check minimum score requirement
            if self.min_score and enrollment.score < self.min_score:
                continue
            
            # Check certificate requirement
            if self.require_certificate and not enrollment.certificate_id:
                continue
            
            # Check renewal requirement
            if self.renewal_required and enrollment.certificate_id:
                certificate = enrollment.certificate_id
                if certificate.expiry_date and certificate.expiry_date < fields.Date.today():
                    continue
            
            # Employee is compliant
            return True
        
        return False
    
    @api.constrains('min_score')
    def _check_min_score(self):
        for rule in self:
            if rule.min_score < 0 or rule.min_score > 100:
                raise ValidationError(_("Minimum score must be between 0 and 100."))
    
    @api.constrains('deadline_date')
    def _check_deadline_date(self):
        for rule in self:
            if rule.deadline_date and rule.deadline_date < fields.Date.today():
                raise ValidationError(_("Deadline date cannot be in the past."))
    
    def action_check_compliance(self):
        """Perform compliance check for all affected employees"""
        self.ensure_one()
        affected_employees = self._get_affected_employees()
        
        compliance_report = []
        for employee in affected_employees:
            is_compliant = self._check_employee_compliance(employee.id)
            compliance_report.append({
                'employee': employee.name,
                'department': employee.department_id.name if employee.department_id else 'N/A',
                'position': employee.job_id.name if employee.job_id else 'N/A',
                'is_compliant': is_compliant,
                'days_until_deadline': (self.deadline_date - fields.Date.today()).days if self.deadline_date else None,
            })
        
        self.write({
            'last_compliance_check': fields.Datetime.now(),
            'next_check_date': fields.Date.today() + timedelta(days=7),
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Compliance Report - {self.name}',
            'res_model': 'lms.compliance.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_rule_id': self.id,
                'default_report_data': str(compliance_report),
            },
        }
    
    def action_send_reminders(self):
        """Send compliance reminders to non-compliant employees"""
        self.ensure_one()
        affected_employees = self._get_affected_employees()
        
        reminder_count = 0
        for employee in affected_employees:
            if not self._check_employee_compliance(employee.id):
                # Check if reminder is due
                if self._should_send_reminder(employee.id):
                    self._send_compliance_reminder(employee)
                    reminder_count += 1
        
        # Log reminder activity
        self.env['lms.compliance.reminder.log'].create({
            'rule_id': self.id,
            'reminder_date': fields.Datetime.now(),
            'employees_notified': reminder_count,
            'reminder_type': 'deadline',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminders Sent'),
                'message': _('Sent %d compliance reminders') % reminder_count,
                'type': 'success',
            }
        }
    
    def _should_send_reminder(self, employee_id):
        """Determine if reminder should be sent to employee"""
        if not self.deadline_date:
            return False
        
        days_until_deadline = (self.deadline_date - fields.Date.today()).days
        
        # Send reminder based on configured days
        if 0 <= days_until_deadline <= self.days_before_deadline_reminder:
            return True
        
        return False
    
    def _send_compliance_reminder(self, employee):
        """Send compliance reminder to employee"""
        template = self.env.ref('lms_marketplace.email_template_compliance_reminder')
        
        context = {
            'employee': employee,
            'rule': self,
            'days_until_deadline': (self.deadline_date - fields.Date.today()).days,
        }
        
        if employee.work_email:
            template.with_context(context).send_mail(self.id, force_send=False)
        
        # Create activity for employee's manager
        if employee.parent_id and employee.parent_id.user_id:
            self.activity_schedule(
                'lms_marketplace.mail_activity_compliance',
                note=_('Compliance reminder sent for %s') % self.name,
                user_id=employee.parent_id.user_id.id,
                date_deadline=self.deadline_date
            )
    
    def action_view_non_compliant(self):
        """View non-compliant employees"""
        self.ensure_one()
        affected_employees = self._get_affected_employees()
        
        non_compliant_ids = []
        for employee in affected_employees:
            if not self._check_employee_compliance(employee.id):
                non_compliant_ids.append(employee.id)
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Non-Compliant Employees - {self.name}',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', non_compliant_ids)],
            'context': {'group_by': 'department_id'},
        }
    
    def action_create_exception(self, employee_id, reason, exception_until):
        """Create exception for an employee"""
        self.ensure_one()
        
        exception = self.env['lms.compliance.exception'].create({
            'rule_id': self.id,
            'employee_id': employee_id,
            'reason': reason,
            'exception_until': exception_until,
            'approved_by_id': self.env.user.partner_id.id,
        })
        
        return exception
    
    def action_generate_report(self):
        """Generate detailed compliance report"""
        self.ensure_one()
        
        report_data = self._generate_detailed_report()
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lms/compliance/report/{self.id}',
            'target': 'new',
        }
    
    def _generate_detailed_report(self):
        """Generate detailed compliance report data"""
        affected_employees = self._get_affected_employees()
        
        report = {
            'rule_info': {
                'name': self.name,
                'code': self.code,
                'deadline': self.deadline_date,
                'course': self.course_id.name,
                'priority': self.priority,
            },
            'summary': {
                'total_affected': len(affected_employees),
                'compliant': 0,
                'non_compliant': 0,
                'exceptions': len(self.exception_ids),
            },
            'department_breakdown': {},
            'employee_details': [],
        }
        
        for employee in affected_employees:
            is_compliant = self._check_employee_compliance(employee.id)
            has_exception = bool(self.exception_ids.filtered(
                lambda e: e.employee_id == employee and e.is_valid
            ))
            
            if is_compliant:
                report['summary']['compliant'] += 1
            else:
                report['summary']['non_compliant'] += 1
            
            # Department breakdown
            dept_name = employee.department_id.name if employee.department_id else 'No Department'
            if dept_name not in report['department_breakdown']:
                report['department_breakdown'][dept_name] = {
                    'total': 0,
                    'compliant': 0,
                    'non_compliant': 0,
                }
            
            report['department_breakdown'][dept_name]['total'] += 1
            if is_compliant:
                report['department_breakdown'][dept_name]['compliant'] += 1
            else:
                report['department_breakdown'][dept_name]['non_compliant'] += 1
            
            # Employee details
            employee_data = {
                'name': employee.name,
                'employee_id': employee.work_contact_id,
                'department': dept_name,
                'position': employee.job_id.name if employee.job_id else 'N/A',
                'status': 'Compliant' if is_compliant else 'Non-Compliant',
                'has_exception': has_exception,
                'exception_until': None,
            }
            
            if has_exception:
                exception = self.exception_ids.filtered(
                    lambda e: e.employee_id == employee and e.is_valid
                )[0]
                employee_data['exception_until'] = exception.exception_until
            
            report['employee_details'].append(employee_data)
        
        return report

class LmsComplianceException(models.Model):
    _name = 'lms.compliance.exception'
    _description = 'LMS Compliance Exception'
    _order = 'exception_until desc'
    
    rule_id = fields.Many2one(
        'lms.compliance.rule',
        string='Compliance Rule',
        required=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )
    
    reason = fields.Text(string='Exception Reason', required=True)
    exception_until = fields.Date(string='Exception Valid Until', required=True)
    approved_by_id = fields.Many2one(
        'res.partner',
        string='Approved By',
        required=True,
        default=lambda self: self.env.user.partner_id
    )
    approval_date = fields.Date(string='Approval Date', default=fields.Date.today)
    
    is_valid = fields.Boolean(
        string='Is Valid',
        compute='_compute_is_valid',
        store=True
    )
    
    @api.depends('exception_until')
    def _compute_is_valid(self):
        for exception in self:
            exception.is_valid = exception.exception_until >= fields.Date.today()
    
    @api.constrains('exception_until')
    def _check_exception_until(self):
        for exception in self:
            if exception.exception_until < fields.Date.today():
                raise ValidationError(_("Exception end date cannot be in the past."))
    
    def action_revoke_exception(self):
        """Revoke the compliance exception"""
        self.ensure_one()
        self.write({'exception_until': fields.Date.today() - timedelta(days=1)})

class LmsComplianceReminderLog(models.Model):
    _name = 'lms.compliance.reminder.log'
    _description = 'LMS Compliance Reminder Log'
    _order = 'reminder_date desc'
    
    rule_id = fields.Many2one(
        'lms.compliance.rule',
        string='Compliance Rule',
        required=True,
        ondelete='cascade'
    )
    
    reminder_date = fields.Datetime(string='Reminder Date', required=True)
    reminder_type = fields.Selection([
        ('deadline', 'Deadline Reminder'),
        ('renewal', 'Renewal Reminder'),
        ('escalation', 'Escalation Reminder'),
    ], string='Reminder Type', required=True)
    
    employees_notified = fields.Integer(string='Employees Notified')
    notification_method = fields.Selection([
        ('email', 'Email'),
        ('system', 'System Notification'),
        ('both', 'Both'),
    ], string='Notification Method', default='email')
    
    details = fields.Text(string='Reminder Details')