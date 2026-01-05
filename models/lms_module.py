from odoo import models, fields, api

class LMSModule(models.Model):
    _name = 'lms.module'
    _description = 'LMS Course Module'
    _order = 'sequence, id'

    name = fields.Char(string='Module Title', required=True)
    description = fields.Text(string='Description')
    course_id = fields.Many2one(
        'lms.course', 
        string='Course', 
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    duration = fields.Float(string='Duration (hours)', compute='_compute_duration')
    
    contents = fields.One2many('lms.content', 'module_id', string='Contents')
    quiz_ids = fields.One2many('lms.quiz', 'module_id', string='Quizzes')
    
    is_preview = fields.Boolean(string='Available as Preview')
    completion_rule = fields.Selection([
        ('all_content', 'Complete All Content'),
        ('quiz_pass', 'Pass Module Quiz'),
        ('either', 'Either Content or Quiz')
    ], string='Completion Rule', default='all_content')
    
    prerequisite_module_ids = fields.Many2many(
        'lms.module',
        'module_prerequisites_rel',
        'module_id',
        'prerequisite_id',
        string='Prerequisite Modules'
    )
    
    @api.depends('contents.duration')
    def _compute_duration(self):
        for module in self:
            module.duration = sum(content.duration for content in module.contents)

class LMSContent(models.Model):
    _name = 'lms.content'
    _description = 'LMS Course Content'
    _order = 'sequence, id'

    name = fields.Char(string='Content Title', required=True)
    module_id = fields.Many2one(
        'lms.module', 
        string='Module', 
        required=True,
        ondelete='cascade'
    )
    content_type = fields.Selection([
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('text', 'Text Article'),
        ('audio', 'Audio'),
        ('scorm', 'SCORM Package'),
        ('url', 'External URL'),
        ('quiz', 'Quiz'),
    ], string='Content Type', required=True, default='video')
    
    sequence = fields.Integer(string='Sequence', default=10)
    duration = fields.Float(string='Duration (minutes)')
    
    # Video specific fields
    video_url = fields.Char(string='Video URL')
    video_file = fields.Binary(string='Video File')
    video_filename = fields.Char(string='Video Filename')
    video_source = fields.Selection([
        ('vimeo', 'Vimeo'),
        ('youtube', 'YouTube'),
        ('html5', 'HTML5 Video'),
        ('s3', 'Amazon S3'),
    ], string='Video Source')
    
    # Document specific fields
    document_file = fields.Binary(string='Document File')
    document_filename = fields.Char(string='Document Filename')
    
    # Text content
    text_content = fields.Html(string='Text Content')
    
    # External URL
    external_url = fields.Char(string='External URL')
    
    # SCORM content
    scorm_file = fields.Binary(string='SCORM File')
    scorm_filename = fields.Char(string='SCORM Filename')
    
    # Quiz reference
    quiz_id = fields.Many2one('lms.quiz', string='Quiz')
    
    is_preview = fields.Boolean(string='Available as Preview')
    is_published = fields.Boolean(string='Published', default=True)
    
    completion_rule = fields.Selection([
        ('view', 'View Content'),
        ('duration', 'Minimum Viewing Duration'),
        ('quiz_pass', 'Pass Associated Quiz')
    ], string='Completion Rule', default='view')
    
    min_view_duration = fields.Float(
        string='Minimum Viewing Duration (minutes)',
        help='Minimum time student must spend on this content to mark as complete'
    )
    
    @api.onchange('content_type')
    def _onchange_content_type(self):
        if self.content_type == 'quiz' and not self.quiz_id:
            self.quiz_id = self.env['lms.quiz'].create({
                'name': f'Quiz for {self.name}',
                'module_id': self.module_id.id,
            })