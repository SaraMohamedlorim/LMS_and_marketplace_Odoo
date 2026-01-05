from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LMSContent(models.Model):
    _name = 'lms.content'
    _description = 'LMS Course Content'
    _order = 'sequence, id'

    name = fields.Char(string='Content Title', required=True, translate=True)
    module_id = fields.Many2one(
        'lms.module', 
        string='Module', 
        required=True,
        ondelete='cascade',
        index=True
    )
    course_id = fields.Many2one(
        'lms.course',
        string='Course',
        related='module_id.course_id',
        store=True,
        readonly=True
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
    duration = fields.Float(string='Duration (minutes)', default=0.0)
    
    # Video specific fields
    video_url = fields.Char(string='Video URL', help='YouTube, Vimeo, or direct video URL')
    video_file = fields.Binary(string='Video File', attachment=True)
    video_filename = fields.Char(string='Video Filename')
    video_source = fields.Selection([
        ('vimeo', 'Vimeo'),
        ('youtube', 'YouTube'),
        ('html5', 'HTML5 Video'),
        ('s3', 'Amazon S3'),
    ], string='Video Source', default='youtube')
    
    # Document specific fields
    document_file = fields.Binary(string='Document File', attachment=True)
    document_filename = fields.Char(string='Document Filename')
    
    # Text content
    text_content = fields.Html(string='Text Content', sanitize=True, translate=True)
    
    # External URL
    external_url = fields.Char(string='External URL', help='Link to external learning resource')
    
    # SCORM content
    scorm_file = fields.Binary(string='SCORM File', attachment=True)
    scorm_filename = fields.Char(string='SCORM Filename')
    
    # Quiz reference
    quiz_id = fields.Many2one('lms.quiz', string='Quiz')
    
    # Preview and publishing
    is_preview = fields.Boolean(string='Available as Preview', help='Make this content available without enrollment')
    is_published = fields.Boolean(string='Published', default=True)
    
    # Completion rules
    completion_rule = fields.Selection([
        ('view', 'View Content'),
        ('duration', 'Minimum Viewing Duration'),
        ('quiz_pass', 'Pass Associated Quiz')
    ], string='Completion Rule', default='view')
    
    min_view_duration = fields.Float(
        string='Minimum Viewing Duration (minutes)',
        default=0.0,
        help='Minimum time student must spend on this content to mark as complete'
    )
    
    # Progress tracking
    progress_ids = fields.One2many('lms.content.progress', 'content_id', string='Student Progress')
    
    # Analytics
    view_count = fields.Integer(string='View Count', compute='_compute_view_count')
    average_completion_time = fields.Float(string='Average Completion Time', compute='_compute_completion_stats')
    completion_rate = fields.Float(string='Completion Rate', compute='_compute_completion_stats')
    
    @api.depends('progress_ids')
    def _compute_view_count(self):
        for content in self:
            content.view_count = len(content.progress_ids.filtered(lambda p: p.state != 'not_started'))
    
    @api.depends('progress_ids')
    def _compute_completion_stats(self):
        for content in self:
            completed_progress = content.progress_ids.filtered(lambda p: p.state == 'completed')
            total_progress = content.progress_ids.filtered(lambda p: p.state != 'not_started')
            
            content.completion_rate = (len(completed_progress) / len(total_progress) * 100) if total_progress else 0
            
            if completed_progress:
                content.average_completion_time = sum(completed_progress.mapped('time_spent')) / len(completed_progress)
            else:
                content.average_completion_time = 0
    
    @api.onchange('content_type')
    def _onchange_content_type(self):
        """Reset fields when content type changes"""
        if self.content_type != 'video':
            self.video_url = False
            self.video_file = False
            self.video_source = 'youtube'
        
        if self.content_type != 'pdf':
            self.document_file = False
        
        if self.content_type != 'text':
            self.text_content = False
        
        if self.content_type != 'url':
            self.external_url = False
        
        if self.content_type != 'scorm':
            self.scorm_file = False
        
        if self.content_type == 'quiz' and not self.quiz_id:
            # Auto-create quiz if none exists
            self.quiz_id = self.env['lms.quiz'].create({
                'name': f'Quiz for {self.name}',
                'module_id': self.module_id.id,
            })
    
    @api.constrains('min_view_duration')
    def _check_min_view_duration(self):
        for content in self:
            if content.completion_rule == 'duration' and content.min_view_duration <= 0:
                raise ValidationError(_("Minimum viewing duration must be greater than 0 when using duration-based completion."))
    
    @api.constrains('quiz_id', 'content_type')
    def _check_quiz_content(self):
        for content in self:
            if content.content_type == 'quiz' and not content.quiz_id:
                raise ValidationError(_("Quiz content must have an associated quiz."))
    
    def get_previous_content(self):
        """Get the previous content in the module"""
        self.ensure_one()
        return self.search([
            ('module_id', '=', self.module_id.id),
            ('sequence', '<', self.sequence),
            ('is_published', '=', True)
        ], order='sequence desc', limit=1)
    
    def get_next_content(self):
        """Get the next content in the module"""
        self.ensure_one()
        return self.search([
            ('module_id', '=', self.module_id.id),
            ('sequence', '>', self.sequence),
            ('is_published', '=', True)
        ], order='sequence asc', limit=1)
    
    def action_view_student_progress(self):
        """View student progress for this content"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Student Progress - {self.name}',
            'res_model': 'lms.content.progress',
            'view_mode': 'tree,form',
            'domain': [('content_id', '=', self.id)],
            'context': {'default_content_id': self.id},
        }
    
    def action_duplicate_content(self):
        """Duplicate the content"""
        self.ensure_one()
        new_content = self.copy(default={
            'name': f"{self.name} (Copy)",
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lms.content',
            'res_id': new_content.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def get_content_url(self, enrollment_id=None):
        """Get the URL for accessing this content"""
        self.ensure_one()
        base_url = self.get_base_url()
        
        if enrollment_id:
            return f"{base_url}/lms/learning/{self.course_id.id}?module={self.module_id.id}&content={self.id}"
        else:
            return f"{base_url}/lms/content/preview/{self.id}"
    
    def mark_as_complete(self, enrollment_id):
        """Mark this content as complete for a student"""
        self.ensure_one()
        progress = self.env['lms.content.progress'].search([
            ('enrollment_id', '=', enrollment_id),
            ('content_id', '=', self.id)
        ], limit=1)
        
        if not progress:
            progress = self.env['lms.content.progress'].create({
                'enrollment_id': enrollment_id,
                'content_id': self.id,
                'state': 'completed',
                'completion_date': fields.Datetime.now(),
            })
        else:
            progress.write({
                'state': 'completed',
                'completion_date': fields.Datetime.now(),
            })
        
        return progress
    
    # Video URL parsing methods
    def get_video_embed_url(self):
        """Get embed URL for video content"""
        self.ensure_one()
        if self.content_type != 'video' or not self.video_url:
            return False
        
        if self.video_source == 'youtube':
            # Extract video ID from YouTube URL
            video_id = self._extract_youtube_id(self.video_url)
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}"
        
        elif self.video_source == 'vimeo':
            # Extract video ID from Vimeo URL
            video_id = self._extract_vimeo_id(self.video_url)
            if video_id:
                return f"https://player.vimeo.com/video/{video_id}"
        
        return self.video_url
    
    def _extract_youtube_id(self, url):
        """Extract YouTube video ID from URL"""
        import re
        patterns = [
            r'(?:youtube\.com\/watch\?v=|\/embed\/|\/v\/|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _extract_vimeo_id(self, url):
        """Extract Vimeo video ID from URL"""
        import re
        patterns = [
            r'vimeo\.com\/(\d+)',
            r'vimeo\.com\/video\/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

class LMSContentProgress(models.Model):
    _name = 'lms.content.progress'
    _description = 'LMS Content Progress Tracking'
    _order = 'completion_date desc'
    
    enrollment_id = fields.Many2one(
        'lms.enrollment', 
        string='Enrollment', 
        required=True,
        ondelete='cascade',
        index=True
    )
    content_id = fields.Many2one(
        'lms.content', 
        string='Content', 
        required=True,
        ondelete='cascade'
    )
    module_id = fields.Many2one(
        'lms.module', 
        string='Module', 
        related='content_id.module_id',
        store=True,
        readonly=True
    )
    course_id = fields.Many2one(
        'lms.course',
        string='Course',
        related='enrollment_id.course_id',
        store=True,
        readonly=True
    )
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        related='enrollment_id.student_id',
        store=True,
        readonly=True
    )
    
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='not_started', tracking=True)
    
    start_date = fields.Datetime(string='Start Date')
    completion_date = fields.Datetime(string='Completion Date')
    time_spent = fields.Float(string='Time Spent (minutes)', default=0.0)
    
    # Quiz attempt reference
    quiz_attempt_id = fields.Many2one('lms.quiz.attempt', string='Quiz Attempt')
    score = fields.Float(string='Score', related='quiz_attempt_id.score', store=True)
    
    # Content-specific data
    last_position = fields.Float(string='Last Position (seconds)', help='Last playback position for video/audio content')
    total_views = fields.Integer(string='Total Views', default=0)
    
    @api.model
    def create(self, vals):
        if 'state' in vals and vals['state'] == 'in_progress' and not vals.get('start_date'):
            vals['start_date'] = fields.Datetime.now()
        return super().create(vals)
    
    def write(self, vals):
        if 'state' in vals:
            if vals['state'] == 'in_progress' and not self.start_date:
                vals['start_date'] = fields.Datetime.now()
            elif vals['state'] == 'completed':
                vals['completion_date'] = fields.Datetime.now()
                # Update total views
                if not vals.get('total_views'):
                    vals['total_views'] = self.total_views + 1
        
        return super().write(vals)
    
    def action_view_content(self):
        """View the associated content"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.content_id.get_content_url(self.enrollment_id.id),
            'target': 'self',
        }
    
    def action_mark_complete(self):
        """Mark content as complete"""
        self.write({
            'state': 'completed',
            'completion_date': fields.Datetime.now(),
        })
    
    def action_reset_progress(self):
        """Reset progress for this content"""
        self.write({
            'state': 'not_started',
            'start_date': False,
            'completion_date': False,
            'time_spent': 0.0,
            'last_position': 0.0,
            'total_views': 0,
        })