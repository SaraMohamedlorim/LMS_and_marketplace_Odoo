from odoo import models, fields, api
import random

class LMSQuiz(models.Model):
    _name = 'lms.quiz'
    _description = 'LMS Quiz/Assessment'
    
    name = fields.Char(string='Quiz Title', required=True)
    module_id = fields.Many2one('lms.module', string='Module')
    course_id = fields.Many2one(
        'lms.course', 
        string='Course', 
        related='module_id.course_id',
        store=True
    )
    
    description = fields.Text(string='Description')
    instructions = fields.Html(string='Instructions')
    
    questions = fields.One2many('lms.question', 'quiz_id', string='Questions')
    question_count = fields.Integer(
        string='Question Count', 
        compute='_compute_question_count'
    )
    
    passing_score = fields.Float(string='Passing Score (%)', default=70.0)
    time_limit = fields.Integer(string='Time Limit (minutes)')
    max_attempts = fields.Integer(string='Maximum Attempts', default=3)
    
    shuffle_questions = fields.Boolean(string='Shuffle Questions', default=True)
    shuffle_answers = fields.Boolean(string='Shuffle Answers', default=True)
    
    show_correct_answers = fields.Boolean(
        string='Show Correct Answers After Submission',
        default=True
    )
    
    require_passing = fields.Boolean(string='Required for Course Completion')
    
    @api.depends('questions')
    def _compute_question_count(self):
        for quiz in self:
            quiz.question_count = len(quiz.questions)
    
    def action_generate_quiz_attempt(self, enrollment):
        """Generate a quiz attempt for a student"""
        questions = self.questions
        if self.shuffle_questions:
            questions = questions.sorted(key=lambda x: random.random())
        
        attempt_questions = []
        for question in questions:
            answers = question.answers
            if self.shuffle_answers:
                answers = answers.sorted(key=lambda x: random.random())
            
            attempt_questions.append((0, 0, {
                'question_id': question.id,
                'student_answers': [(6, 0, answers.ids)],
            }))
        
        return self.env['lms.quiz.attempt'].create({
            'quiz_id': self.id,
            'enrollment_id': enrollment.id,
            'student_id': enrollment.student_id.id,
            'questions': attempt_questions,
            'time_limit': self.time_limit,
        })

class LMSQuestion(models.Model):
    _name = 'lms.question'
    _description = 'LMS Quiz Question'
    _order = 'sequence, id'
    
    name = fields.Html(string='Question', required=True)
    quiz_id = fields.Many2one('lms.quiz', string='Quiz', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    question_type = fields.Selection([
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
        ('matching', 'Matching'),
    ], string='Question Type', required=True, default='multiple_choice')
    
    answers = fields.One2many('lms.answer', 'question_id', string='Answers')
    points = fields.Float(string='Points', default=1.0)
    
    explanation = fields.Html(string='Explanation', help='Explanation shown after answering')
    
    @api.constrains('question_type', 'answers')
    def _check_answers(self):
        for question in self:
            if question.question_type in ['multiple_choice', 'true_false']:
                if not question.answers:
                    raise ValidationError(_("Multiple choice questions must have answers."))
                
                correct_answers = question.answers.filtered(lambda a: a.is_correct)
                if not correct_answers:
                    raise ValidationError(_("At least one answer must be marked as correct."))

class LMSAnswer(models.Model):
    _name = 'lms.answer'
    _description = 'LMS Question Answer'
    _order = 'sequence, id'
    
    question_id = fields.Many2one('lms.question', string='Question', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    text = fields.Html(string='Answer Text', required=True)
    is_correct = fields.Boolean(string='Is Correct')
    feedback = fields.Text(string='Feedback', help='Feedback shown when this answer is selected')

class LMSQuizAttempt(models.Model):
    _name = 'lms.quiz.attempt'
    _description = 'LMS Quiz Attempt'
    _order = 'create_date desc'
    
    quiz_id = fields.Many2one('lms.quiz', string='Quiz', required=True)
    enrollment_id = fields.Many2one('lms.enrollment', string='Enrollment', required=True)
    student_id = fields.Many2one('res.partner', string='Student', required=True)
    
    attempt_number = fields.Integer(string='Attempt Number', default=1)
    start_time = fields.Datetime(string='Start Time', default=fields.Datetime.now)
    end_time = fields.Datetime(string='End Time')
    
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
    ], string='Status', default='in_progress')
    
    questions = fields.One2many('lms.quiz.attempt.question', 'attempt_id', string='Questions')
    
    score = fields.Float(string='Score (%)', compute='_compute_score')
    total_points = fields.Float(string='Total Points', compute='_compute_score')
    earned_points = fields.Float(string='Earned Points', compute='_compute_score')
    
    time_spent = fields.Float(string='Time Spent (minutes)', compute='_compute_time_spent')
    time_limit = fields.Integer(string='Time Limit (minutes)')
    
    is_passed = fields.Boolean(string='Passed', compute='_compute_is_passed')
    
    @api.depends('questions.points_earned')
    def _compute_score(self):
        for attempt in self:
            total_points = sum(attempt.questions.mapped('points_possible'))
            earned_points = sum(attempt.questions.mapped('points_earned'))
            
            attempt.total_points = total_points
            attempt.earned_points = earned_points
            attempt.score = (earned_points / total_points * 100) if total_points > 0 else 0
    
    @api.depends('start_time', 'end_time')
    def _compute_time_spent(self):
        for attempt in self:
            if attempt.start_time and attempt.end_time:
                delta = attempt.end_time - attempt.start_time
                attempt.time_spent = delta.total_seconds() / 60
            else:
                attempt.time_spent = 0
    
    @api.depends('score', 'quiz_id.passing_score')
    def _compute_is_passed(self):
        for attempt in self:
            attempt.is_passed = attempt.score >= attempt.quiz_id.passing_score
    
    def action_submit_quiz(self):
        self.write({
            'state': 'submitted',
            'end_time': fields.Datetime.now()
        })
        
        # Auto-grade if possible
        self._auto_grade_quiz()
        
        # Update content progress if this quiz is associated with content
        content_progress = self.env['lms.content.progress'].search([
            ('enrollment_id', '=', self.enrollment_id.id),
            ('quiz_attempt_id', '=', self.id)
        ])
        
        if content_progress:
            content_progress.write({
                'state': 'completed',
                'completion_date': fields.Datetime.now()
            })
    
    def _auto_grade_quiz(self):
        """Automatically grade questions that can be auto-graded"""
        for attempt_question in self.questions:
            if attempt_question.question_id.question_type in ['multiple_choice', 'true_false']:
                attempt_question._auto_grade()
        
        self.write({'state': 'graded'})

class LMSQuizAttemptQuestion(models.Model):
    _name = 'lms.quiz.attempt.question'
    _description = 'LMS Quiz Attempt Question'
    
    attempt_id = fields.Many2one('lms.quiz.attempt', string='Attempt', required=True)
    question_id = fields.Many2one('lms.question', string='Question', required=True)
    
    student_answer_ids = fields.Many2many(
        'lms.answer',
        'quiz_attempt_answer_rel',
        'attempt_question_id',
        'answer_id',
        string='Student Answers'
    )
    
    student_essay_answer = fields.Text(string='Essay Answer')
    
    points_possible = fields.Float(
        string='Possible Points', 
        related='question_id.points'
    )
    points_earned = fields.Float(string='Points Earned', default=0.0)
    
    is_correct = fields.Boolean(string='Is Correct', compute='_compute_is_correct')
    
    @api.depends('student_answer_ids', 'question_id', 'points_earned')
    def _compute_is_correct(self):
        for attempt_question in self:
            if attempt_question.question_id.question_type in ['multiple_choice', 'true_false']:
                correct_answers = attempt_question.question_id.answers.filtered(
                    lambda a: a.is_correct
                )
                student_correct_answers = attempt_question.student_answer_ids.filtered(
                    lambda a: a.is_correct
                )
                attempt_question.is_correct = (
                    len(correct_answers) == len(student_correct_answers) and
                    len(attempt_question.student_answer_ids) == len(correct_answers)
                )
            else:
                attempt_question.is_correct = attempt_question.points_earned > 0
    
    def _auto_grade(self):
        """Auto-grade multiple choice and true/false questions"""
        if self.question_id.question_type in ['multiple_choice', 'true_false']:
            correct_answers = self.question_id.answers.filtered(lambda a: a.is_correct)
            student_correct_answers = self.student_answer_ids.filtered(lambda a: a.is_correct)
            
            if (len(correct_answers) == len(student_correct_answers) and
                len(self.student_answer_ids) == len(correct_answers)):
                self.points_earned = self.points_possible
            else:
                self.points_earned = 0