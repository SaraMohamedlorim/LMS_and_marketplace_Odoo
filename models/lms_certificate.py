from odoo import models, fields, api
import hashlib
import uuid

class LMSCertificate(models.Model):
    _name = 'lms.certificate'
    _description = 'LMS Certificate'
    _rec_name = 'display_name'
    
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    
    student_id = fields.Many2one('res.partner', string='Student', required=True)
    course_id = fields.Many2one('lms.course', string='Course', required=True)
    enrollment_id = fields.Many2one('lms.enrollment', string='Enrollment', required=True)
    
    certificate_number = fields.Char(
        string='Certificate Number',
        default=lambda self: self._generate_certificate_number(),
        readonly=True
    )
    
    issue_date = fields.Datetime(string='Issue Date', required=True)
    expiry_date = fields.Datetime(string='Expiry Date')
    
    template_id = fields.Many2one(
        'lms.certificate.template',
        string='Certificate Template',
        required=True
    )
    
    score = fields.Float(string='Final Score', related='enrollment_id.score')
    grade = fields.Char(string='Grade', compute='_compute_grade')
    
    verification_hash = fields.Char(
        string='Verification Hash',
        compute='_compute_verification_hash',
        store=True
    )
    
    pdf_certificate = fields.Binary(string='PDF Certificate')
    pdf_filename = fields.Char(string='PDF Filename')
    
    is_valid = fields.Boolean(string='Is Valid', compute='_compute_is_valid')
    
    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for certificate in self:
            certificate.display_name = f"{certificate.student_id.name} - {certificate.course_id.name}"
    
    def _generate_certificate_number(self):
        return f"CERT-{uuid.uuid4().hex[:12].upper()}"
    
    @api.depends('certificate_number', 'student_id', 'course_id', 'issue_date')
    def _compute_verification_hash(self):
        for certificate in self:
            data = f"{certificate.certificate_number}{certificate.student_id.id}{certificate.course_id.id}{certificate.issue_date}"
            certificate.verification_hash = hashlib.sha256(data.encode()).hexdigest()
    
    @api.depends('score')
    def _compute_grade(self):
        for certificate in self:
            if certificate.score >= 90:
                certificate.grade = 'A'
            elif certificate.score >= 80:
                certificate.grade = 'B'
            elif certificate.score >= 70:
                certificate.grade = 'C'
            elif certificate.score >= 60:
                certificate.grade = 'D'
            else:
                certificate.grade = 'F'
    
    @api.depends('expiry_date')
    def _compute_is_valid(self):
        for certificate in self:
            if certificate.expiry_date:
                certificate.is_valid = fields.Datetime.now() < certificate.expiry_date
            else:
                certificate.is_valid = True
    
    def action_generate_pdf(self):
        """Generate PDF certificate"""
        # Implementation for PDF generation using reportlab or wkhtmltopdf
        pass
    
    def action_verify_certificate(self):
        """Verify certificate authenticity"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lms/certificate/verify/{self.verification_hash}',
            'target': 'new',
        }

class LMSCertificateTemplate(models.Model):
    _name = 'lms.certificate.template'
    _description = 'LMS Certificate Template'
    
    name = fields.Char(string='Template Name', required=True)
    template_file = fields.Binary(string='Template File', required=True)
    template_filename = fields.Char(string='Template Filename')
    
    background_image = fields.Binary(string='Background Image')
    signature_image = fields.Binary(string='Signature Image')
    
    template_html = fields.Html(string='HTML Template')
    
    is_active = fields.Boolean(string='Active', default=True)