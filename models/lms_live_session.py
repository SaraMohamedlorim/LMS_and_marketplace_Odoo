from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta

class LmsLiveSession(models.Model):
    _name = 'lms.live.session'
    _description = 'LMS Live Session/Webinar'
    _order = 'start_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Session Title', required=True, tracking=True)
    description = fields.Html(string='Description')
    course_id = fields.Many2one(
        'lms.course',
        string='Course',
        required=True,
        tracking=True
    )
    instructor_id = fields.Many2one(
        'res.partner',
        string='Instructor',
        required=True,
        domain=[('is_instructor', '=', True)],
        tracking=True
    )
    
    start_time = fields.Datetime(string='Start Time', required=True, tracking=True)
    duration = fields.Integer(string='Duration (minutes)', required=True, default=60)
    end_time = fields.Datetime(
        string='End Time',
        compute='_compute_end_time',
        store=True
    )
    
    timezone = fields.Selection([
        ('UTC', 'UTC'),
        ('EST', 'Eastern Time'),
        ('PST', 'Pacific Time'),
        ('CET', 'Central European Time'),
        ('IST', 'Indian Standard Time'),
        ('GST', 'Gulf Standard Time'),
    ], string='Timezone', default='UTC', required=True)
    
    # Session Type
    session_type = fields.Selection([
        ('live_lecture', 'Live Lecture'),
        ('qna', 'Q&A Session'),
        ('workshop', 'Workshop'),
        ('office_hours', 'Office Hours'),
        ('review_session', 'Review Session'),
    ], string='Session Type', default='live_lecture')
    
    # Platform Integration
    platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('meet', 'Google Meet'),
        ('bigbluebutton', 'BigBlueButton'),
        ('custom', 'Custom Platform'),
    ], string='Platform', default='zoom', required=True)
    
    meeting_id = fields.Char(string='Meeting ID')
    meeting_password = fields.Char(string='Meeting Password')
    join_url = fields.Char(string='Join URL')
    recording_url = fields.Char(string='Recording URL')
    
    # Capacity and Registration
    max_participants = fields.Integer(string='Maximum Participants')
    registered_participants = fields.Integer(
        string='Registered Participants',
        compute='_compute_registered_participants'
    )
    available_seats = fields.Integer(
        string='Available Seats',
        compute='_compute_available_seats'
    )
    
    # Registration Management
    require_registration = fields.Boolean(string='Require Registration', default=True)
    registration_deadline = fields.Datetime(string='Registration Deadline')
    auto_approve_registrations = fields.Boolean(string='Auto-approve Registrations', default=True)
    
    # Session Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('live', 'Live Now'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    # Participants
    enrolled_students = fields.Many2many(
        'res.partner',
        'live_session_enrollment_rel',
        'session_id',
        'student_id',
        string='Enrolled Students',
        domain=[('is_learner', '=', True)]
    )
    
    attendance_ids = fields.One2many(
        'lms.live.session.attendance',
        'session_id',
        string='Attendance Records'
    )
    
    attendance_count = fields.Integer(
        string='Attendance Count',
        compute='_compute_attendance_stats'
    )
    attendance_rate = fields.Float(
        string='Attendance Rate',
        compute='_compute_attendance_stats'
    )
    
    # Materials
    presentation_file = fields.Binary(string='Presentation File')
    presentation_filename = fields.Char(string='Presentation Filename')
    resource_ids = fields.Many2many(
        'ir.attachment',
        string='Session Resources'
    )
    
    # Chat and Interaction
    chat_log = fields.Text(string='Chat Log')
    qna_questions = fields.One2many(
        'lms.live.session.question',
        'session_id',
        string='Q&A Questions'
    )
    
    # Recurring Sessions
    is_recurring = fields.Boolean(string='Recurring Session')
    recurrence_pattern = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ], string='Recurrence Pattern')
    recurrence_end_date = fields.Datetime(string='Recurrence End Date')
    
    @api.depends('start_time', 'duration')
    def _compute_end_time(self):
        for session in self:
            if session.start_time and session.duration:
                session.end_time = session.start_time + timedelta(minutes=session.duration)
            else:
                session.end_time = False
    
    @api.depends('enrolled_students')
    def _compute_registered_participants(self):
        for session in self:
            session.registered_participants = len(session.enrolled_students)
    
    @api.depends('max_participants', 'registered_participants')
    def _compute_available_seats(self):
        for session in self:
            if session.max_participants:
                session.available_seats = session.max_participants - session.registered_participants
            else:
                session.available_seats = 999  # Unlimited
    
    @api.depends('attendance_ids')
    def _compute_attendance_stats(self):
        for session in self:
            attended = session.attendance_ids.filtered(lambda a: a.status == 'attended')
            session.attendance_count = len(attended)
            
            if session.registered_participants > 0:
                session.attendance_rate = (len(attended) / session.registered_participants) * 100
            else:
                session.attendance_rate = 0
    
    @api.constrains('max_participants', 'registered_participants')
    def _check_capacity(self):
        for session in self:
            if session.max_participants and session.registered_participants > session.max_participants:
                raise ValidationError(_("Registered participants exceed maximum capacity."))
    
    @api.constrains('start_time', 'end_time')
    def _check_session_time(self):
        for session in self:
            if session.start_time and session.end_time and session.start_time >= session.end_time:
                raise ValidationError(_("Session end time must be after start time."))
    
    def action_schedule(self):
        """Schedule the live session"""
        self.write({'status': 'scheduled'})
        
        # Create calendar event for participants
        self._create_calendar_event()
        
        # Send invitation emails
        self._send_invitations()
    
    def action_start(self):
        """Mark session as live"""
        self.write({'status': 'live'})
        
        # Record start time
        self.activity_schedule(
            'lms_marketplace.mail_activity_live_session',
            note=_('Live session started'),
            user_id=self.instructor_id.user_id.id
        )
    
    def action_end(self):
        """Mark session as completed"""
        self.write({'status': 'completed'})
        
        # Generate attendance report
        self._generate_attendance_report()
        
        # Send follow-up emails
        self._send_follow_up()
    
    def action_cancel(self):
        """Cancel the session"""
        if self.status == 'live':
            raise UserError(_("Cannot cancel a live session. Please end it first."))
        
        self.write({'status': 'cancelled'})
        
        # Send cancellation notifications
        self._send_cancellation_notice()
    
    def action_register_student(self, student_id):
        """Register a student for the session"""
        self.ensure_one()
        
        if student_id not in self.enrolled_students.ids:
            if self.require_registration and self.available_seats <= 0:
                raise UserError(_("No available seats for this session."))
            
            if self.registration_deadline and fields.Datetime.now() > self.registration_deadline:
                raise UserError(_("Registration deadline has passed."))
            
            self.write({
                'enrolled_students': [(4, student_id)]
            })
            
            # Send confirmation email
            self._send_registration_confirmation(student_id)
            
            return True
        
        return False
    
    def _create_calendar_event(self):
        """Create calendar event for the session"""
        attendees = [(4, student.user_id.id) for student in self.enrolled_students if student.user_id]
        
        calendar_event = self.env['calendar.event'].create({
            'name': self.name,
            'description': self.description,
            'start': self.start_time,
            'stop': self.end_time,
            'duration': self.duration,
            'partner_ids': [(4, self.instructor_id.id)] + attendees,
            'location': self.join_url or 'Online',
            'videocall_location': self.join_url,
            'privacy': 'public' if not self.require_registration else 'private',
        })
        
        return calendar_event
    
    def _send_invitations(self):
        """Send invitation emails to enrolled students"""
        # Implementation for sending emails
        template = self.env.ref('lms_marketplace.email_template_live_session_invitation')
        for student in self.enrolled_students:
            if student.email:
                template.with_context({
                    'session': self,
                    'student': student,
                }).send_mail(self.id, force_send=False)
    
    def _generate_attendance_report(self):
        """Generate attendance report after session ends"""
        for student in self.enrolled_students:
            attendance_status = 'absent'  # Default to absent
            
            # In real implementation, this would check actual attendance data
            # from the meeting platform API
            
            self.env['lms.live.session.attendance'].create({
                'session_id': self.id,
                'student_id': student.id,
                'status': attendance_status,
                'join_time': self.start_time,
                'leave_time': self.end_time,
                'duration': self.duration if attendance_status == 'attended' else 0,
            })
    
    def action_view_attendance(self):
        """View attendance records for this session"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendance - {self.name}',
            'res_model': 'lms.live.session.attendance',
            'view_mode': 'tree,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'default_session_id': self.id},
        }
    
    def action_join_session(self):
        """Join the live session"""
        self.ensure_one()
        if self.status != 'live' and self.status != 'scheduled':
            raise UserError(_("Session is not currently active or scheduled."))
        
        if not self.join_url:
            raise UserError(_("No join URL configured for this session."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': self.join_url,
            'target': 'new',
        }

class LmsLiveSessionAttendance(models.Model):
    _name = 'lms.live.session.attendance'
    _description = 'LMS Live Session Attendance'
    _order = 'join_time desc'
    
    session_id = fields.Many2one(
        'lms.live.session',
        string='Session',
        required=True,
        ondelete='cascade'
    )
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        domain=[('is_learner', '=', True)]
    )
    
    status = fields.Selection([
        ('registered', 'Registered'),
        ('attended', 'Attended'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ], string='Attendance Status', default='registered')
    
    join_time = fields.Datetime(string='Join Time')
    leave_time = fields.Datetime(string='Leave Time')
    duration = fields.Float(string='Duration (minutes)', compute='_compute_duration')
    
    notes = fields.Text(string='Notes')
    
    @api.depends('join_time', 'leave_time')
    def _compute_duration(self):
        for attendance in self:
            if attendance.join_time and attendance.leave_time:
                delta = attendance.leave_time - attendance.join_time
                attendance.duration = delta.total_seconds() / 60
            else:
                attendance.duration = 0

class LmsLiveSessionQuestion(models.Model):
    _name = 'lms.live.session.question'
    _description = 'LMS Live Session Q&A'
    _order = 'create_date desc'
    
    session_id = fields.Many2one(
        'lms.live.session',
        string='Session',
        required=True,
        ondelete='cascade'
    )
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        domain=[('is_learner', '=', True)]
    )
    
    question = fields.Text(string='Question', required=True)
    answer = fields.Text(string='Answer')
    answered_by_id = fields.Many2one(
        'res.partner',
        string='Answered By',
        domain=[('is_instructor', '=', True)]
    )
    answer_time = fields.Datetime(string='Answer Time')
    
    is_anonymous = fields.Boolean(string='Ask Anonymously')
    is_answered = fields.Boolean(string='Answered', compute='_compute_is_answered')
    
    @api.depends('answer', 'answered_by_id')
    def _compute_is_answered(self):
        for question in self:
            question.is_answered = bool(question.answer and question.answered_by_id)