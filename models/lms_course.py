from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LMSCourse(models.Model):
    _name = 'lms.course'
    _description = 'LMS Course'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Course Title', required=True, tracking=True)
    subtitle = fields.Char(string='Subtitle')
    description = fields.Html(string='Description')
    short_description = fields.Text(string='Short Description')
    
    instructor_id = fields.Many2one(
        'res.partner', 
        string='Instructor', 
        domain=[('is_instructor', '=', True)],
        required=True,
        tracking=True
    )
    
    category_id = fields.Many2one(
        'lms.category', 
        string='Category',
        tracking=True
    )
    
    tags = fields.Many2many('lms.tag', string='Tags')
    level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('all', 'All Levels')
    ], string='Difficulty Level', default='all')
    
    price = fields.Float(string='Price', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    discount_price = fields.Float(string='Discount Price')
    is_free = fields.Boolean(string='Free Course', compute='_compute_is_free')
    
    image = fields.Binary(string='Course Image')
    promotional_video = fields.Char(string='Promotional Video URL')
    
    duration = fields.Float(string='Total Duration (hours)', compute='_compute_duration')
    total_modules = fields.Integer(string='Total Modules', compute='_compute_total_modules')
    total_lectures = fields.Integer(string='Total Lectures', compute='_compute_total_lectures')
    
    modules = fields.One2many('lms.module', 'course_id', string='Modules')
    enrollments = fields.One2many('lms.enrollment', 'course_id', string='Enrollments')
    
    published = fields.Boolean(string='Published', default=False, tracking=True)
    published_date = fields.Datetime(string='Published Date')
    
    language = fields.Selection([
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('ar', 'Arabic'),
    ], string='Language', default='en')
    
    requirements = fields.Html(string='Requirements')
    learning_outcomes = fields.Html(string='What You\'ll Learn')
    
    target_audience = fields.Text(string='Target Audience')
    certificate_template = fields.Many2one(
        'lms.certificate.template', 
        string='Certificate Template'
    )
    
    max_students = fields.Integer(string='Maximum Students')
    current_students = fields.Integer(
        string='Current Students', 
        compute='_compute_current_students'
    )
    
    rating_avg = fields.Float(string='Average Rating', compute='_compute_ratings')
    rating_count = fields.Integer(string='Rating Count', compute='_compute_ratings')
    
    sequence = fields.Integer(string='Sequence', default=10)
    website_id = fields.Many2one('website', string='Website')
    
    scorm_package = fields.Binary(string='SCORM Package')
    scorm_file_name = fields.Char(string='SCORM File Name')
    
    corporate_only = fields.Boolean(string='Corporate Only')
    allowed_companies = fields.Many2many(
        'res.company', 
        string='Allowed Companies'
    )
    
    @api.depends('price')
    def _compute_is_free(self):
        for course in self:
            course.is_free = course.price == 0
    
    @api.depends('modules.duration')
    def _compute_duration(self):
        for course in self:
            course.duration = sum(module.duration for module in course.modules)
    
    @api.depends('modules')
    def _compute_total_modules(self):
        for course in self:
            course.total_modules = len(course.modules)
    
    @api.depends('modules.contents')
    def _compute_total_lectures(self):
        for course in self:
            course.total_lectures = sum(
                len(module.contents) for module in course.modules
            )
    
    @api.depends('enrollments')
    def _compute_current_students(self):
        for course in self:
            course.current_students = len(course.enrollments.filtered(
                lambda e: e.state == 'in_progress'
            ))
    
    def _compute_ratings(self):
        # Implementation for rating calculations
        pass
    
    def action_publish(self):
        self.write({
            'published': True,
            'published_date': fields.Datetime.now()
        })
    
    def action_unpublish(self):
        self.write({'published': False})
    
    def action_view_enrollments(self):
        action = self.env.ref('lms_marketplace.lms_enrollment_action').read()[0]
        action['domain'] = [('course_id', '=', self.id)]
        return action
    
    @api.constrains('max_students', 'current_students')
    def _check_max_students(self):
        for course in self:
            if course.max_students and course.current_students > course.max_students:
                raise ValidationError(_(
                    "Number of enrolled students exceeds maximum allowed students."
                ))

class LMSCategory(models.Model):
    _name = 'lms.category'
    _description = 'LMS Course Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    parent_id = fields.Many2one('lms.category', string='Parent Category')
    description = fields.Text(string='Description')
    image = fields.Binary(string='Category Image')
    sequence = fields.Integer(string='Sequence', default=10)
    course_count = fields.Integer(
        string='Course Count', 
        compute='_compute_course_count'
    )
    
    def _compute_course_count(self):
        for category in self:
            category.course_count = self.env['lms.course'].search_count([
                ('category_id', '=', category.id),
                ('published', '=', True)
            ])

class LMSTag(models.Model):
    _name = 'lms.tag'
    _description = 'LMS Course Tag'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')