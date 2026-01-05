from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LmsAchievementType(models.Model):
    _name = 'lms.achievement.type'
    _description = 'LMS Achievement Type'
    _order = 'sequence, id'
    
    name = fields.Char(string='Achievement Name', required=True, translate=True)
    description = fields.Text(string='Description')
    points = fields.Integer(string='Points Awarded', default=10)
    badge_id = fields.Many2one(
        'gamification.badge',
        string='Associated Badge',
        help='Badge to award when this achievement is earned'
    )
    # badge_image = fields.Binary(string='Badge Image', related='badge_id.image', store=False)
    sequence = fields.Integer(string='Sequence', default=10)
    is_active = fields.Boolean(string='Active', default=True)
    
    # Achievement Criteria
    criteria_type = fields.Selection([
        ('course_completion', 'Course Completion'),
        ('quiz_score', 'Quiz Score'),
        ('time_spent', 'Time Spent Learning'),
        ('streak_days', 'Learning Streak'),
        ('social_engagement', 'Social Engagement'),
        ('custom', 'Custom Criteria'),
    ], string='Criteria Type', required=True, default='course_completion')
    
    # Criteria details based on type
    required_course_id = fields.Many2one('lms.course', string='Required Course')
    required_quiz_id = fields.Many2one('lms.quiz', string='Required Quiz')
    min_quiz_score = fields.Float(string='Minimum Quiz Score (%)', default=80.0)
    min_time_hours = fields.Float(string='Minimum Time (hours)', default=10.0)
    streak_days_required = fields.Integer(string='Streak Days Required', default=7)
    social_actions_required = fields.Integer(string='Social Actions Required', default=5)
    custom_criteria = fields.Text(string='Custom Criteria Description')
    
    # Achievement stats
    total_awards = fields.Integer(
        string='Total Awards',
        compute='_compute_award_stats'
    )
    recent_awards = fields.Integer(
        string='Recent Awards (30 days)',
        compute='_compute_award_stats'
    )
    
    @api.depends('badge_id')
    def _compute_award_stats(self):
        for achievement_type in self:
            if achievement_type.badge_id:
                badge_users = self.env['gamification.badge.user'].search([
                    ('badge_id', '=', achievement_type.badge_id.id)
                ])
                achievement_type.total_awards = len(badge_users)
                
                recent_date = fields.Datetime.now() - fields.timedelta(days=30)
                recent_badge_users = badge_users.filtered(
                    lambda bu: bu.create_date >= recent_date
                )
                achievement_type.recent_awards = len(recent_badge_users)
            else:
                achievement_type.total_awards = 0
                achievement_type.recent_awards = 0
    
    @api.constrains('min_quiz_score')
    def _check_min_quiz_score(self):
        for achievement in self:
            if achievement.criteria_type == 'quiz_score' and not (0 <= achievement.min_quiz_score <= 100):
                raise ValidationError(_("Minimum quiz score must be between 0 and 100."))
    
    def action_view_awarded_students(self):
        """View students who earned this achievement"""
        self.ensure_one()
        if not self.badge_id:
            return {'warning': _("No badge associated with this achievement type.")}
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Students with {self.name}',
            'res_model': 'gamification.badge.user',
            'view_mode': 'tree,form',
            'domain': [('badge_id', '=', self.badge_id.id)],
            'context': {'group_by': 'user_id'},
        }

class LmsAchievement(models.Model):
    _name = 'lms.achievement'
    _description = 'LMS Student Achievement'
    _order = 'award_date desc'
    _rec_name = 'display_name'
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        domain=[('is_learner', '=', True)],
        index=True
    )
    achievement_type_id = fields.Many2one(
        'lms.achievement.type',
        string='Achievement Type',
        required=True
    )
    badge_id = fields.Many2one(
        'gamification.badge',
        string='Badge',
        related='achievement_type_id.badge_id',
        store=True
    )
    
    award_date = fields.Datetime(
        string='Award Date',
        default=fields.Datetime.now,
        required=True
    )
    points_awarded = fields.Integer(
        string='Points Awarded',
        related='achievement_type_id.points',
        store=True
    )
    
    # Context data
    course_id = fields.Many2one('lms.course', string='Related Course')
    quiz_id = fields.Many2one('lms.quiz', string='Related Quiz')
    quiz_score = fields.Float(string='Quiz Score (%)')
    time_spent = fields.Float(string='Time Spent (hours)')
    streak_days = fields.Integer(string='Streak Days')
    
    context_data = fields.Text(
        string='Context Data',
        help='Additional context about how achievement was earned'
    )
    
    # Status
    is_notified = fields.Boolean(string='Student Notified', default=False)
    is_public = fields.Boolean(string='Public Achievement', default=True)
    
    # Achievement details
    achievement_name = fields.Char(
        string='Achievement Name',
        related='achievement_type_id.name',
        store=True
    )
    achievement_description = fields.Text(
        string='Description',
        related='achievement_type_id.description',
        store=True
    )
    
    @api.depends('student_id', 'achievement_type_id', 'award_date')
    def _compute_display_name(self):
        for achievement in self:
            achievement.display_name = f"{achievement.student_id.name} - {achievement.achievement_type_id.name} - {achievement.award_date.strftime('%Y-%m-%d') if achievement.award_date else ''}"
    
    @api.model
    def create(self, vals):
        """Override create to update student points"""
        achievement = super().create(vals)
        
        # Update student's total points
        if achievement.student_id and achievement.points_awarded:
            achievement.student_id.write({
                'lms_points': achievement.student_id.lms_points + achievement.points_awarded
            })
        
        # Check for level upgrade
        achievement._check_level_upgrade()
        
        return achievement
    
    def _check_level_upgrade(self):
        """Check if student should level up based on total points"""
        for achievement in self:
            student = achievement.student_id
            total_points = student.lms_points
            
            # Define level thresholds
            level_thresholds = {
                1: 0,      # Beginner
                2: 100,    # Intermediate
                3: 300,    # Advanced
                4: 600,    # Expert
                5: 1000,   # Master
            }
            
            current_level = student.lms_level or 1
            
            for level, threshold in sorted(level_thresholds.items(), reverse=True):
                if total_points >= threshold and level > current_level:
                    student.write({'lms_level': level})
                    
                    # Create level up achievement
                    level_up_type = self.env['lms.achievement.type'].search([
                        ('name', 'ilike', f'Level {level}'),
                        ('criteria_type', '=', 'custom')
                    ], limit=1)
                    
                    if not level_up_type:
                        level_up_type = self.env['lms.achievement.type'].create({
                            'name': f'Level {level} Achiever',
                            'description': f'Reached Level {level} in the learning journey',
                            'points': level * 50,
                            'criteria_type': 'custom',
                            'custom_criteria': f'Accumulated {threshold}+ total learning points',
                        })
                    
                    self.create({
                        'student_id': student.id,
                        'achievement_type_id': level_up_type.id,
                        'award_date': fields.Datetime.now(),
                        'context_data': f'Reached {total_points} total points',
                    })
                    break
    
    def action_notify_student(self):
        """Send notification to student about achievement"""
        self.ensure_one()
        # Implementation for sending notification
        self.write({'is_notified': True})
        return {'type': 'ir.actions.act_window_close'}
    
    def action_share_achievement(self):
        """Share achievement on social media or platform"""
        self.ensure_one()
        # Implementation for sharing
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lms/achievement/share/{self.id}',
            'target': 'new',
        }
    
    def action_view_badge(self):
        """View associated badge"""
        self.ensure_one()
        if self.badge_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.badge_id.name,
                'res_model': 'gamification.badge',
                'res_id': self.badge_id.id,
                'view_mode': 'form',
                'target': 'current',
            }