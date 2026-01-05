from odoo import models, fields, api
from datetime import datetime, timedelta

class LMSAnalytics(models.Model):
    _name = 'lms.analytics'
    _description = 'LMS Analytics and Reporting'
    _auto = False
    
    @api.model
    def get_course_analytics(self, course_id=None, date_from=None, date_to=None):
        """Get comprehensive analytics for courses"""
        domain = []
        if course_id:
            domain.append(('course_id', '=', course_id))
        if date_from:
            domain.append(('enrollment_date', '>=', date_from))
        if date_to:
            domain.append(('enrollment_date', '<=', date_to))
        
        enrollments = self.env['lms.enrollment'].search(domain)
        
        analytics = {
            'total_enrollments': len(enrollments),
            'completed_enrollments': len(enrollments.filtered(lambda e: e.state == 'completed')),
            'completion_rate': 0,
            'average_progress': 0,
            'average_score': 0,
            'revenue': 0,
        }
        
        if analytics['total_enrollments'] > 0:
            analytics['completion_rate'] = (
                analytics['completed_enrollments'] / analytics['total_enrollments'] * 100
            )
            analytics['average_progress'] = sum(
                enrollment.progress for enrollment in enrollments
            ) / analytics['total_enrollments']
            analytics['average_score'] = sum(
                enrollment.score for enrollment in enrollments if enrollment.score
            ) / len([e for e in enrollments if e.score])
            
            paid_enrollments = enrollments.filtered(
                lambda e: e.payment_status == 'paid' and not e.course_id.is_free
            )
            analytics['revenue'] = sum(
                enrollment.course_id.price for enrollment in paid_enrollments
            )
        
        return analytics
    
    @api.model
    def get_student_progress(self, student_id, course_id=None):
        """Get detailed progress analytics for a student"""
        domain = [('student_id', '=', student_id)]
        if course_id:
            domain.append(('course_id', '=', course_id))
        
        enrollments = self.env['lms.enrollment'].search(domain)
        
        progress_data = []
        for enrollment in enrollments:
            course_data = {
                'course_name': enrollment.course_id.name,
                'progress': enrollment.progress,
                'score': enrollment.score,
                'enrollment_date': enrollment.enrollment_date,
                'completion_date': enrollment.completion_date,
                'time_spent': 0,  # Would calculate from content progress
                'certificate_issued': bool(enrollment.certificate_id),
            }
            progress_data.append(course_data)
        
        return progress_data
    
    @api.model
    def get_corporate_training_report(self, company_id, date_from=None, date_to=None):
        """Generate corporate training report"""
        domain = [('company_id', '=', company_id)]
        if date_from:
            domain.append(('enrollment_date', '>=', date_from))
        if date_to:
            domain.append(('enrollment_date', '<=', date_to))
        
        enrollments = self.env['lms.enrollment'].search(domain)
        employees = self.env['hr.employee'].search([('company_id', '=', company_id)])
        
        report = {
            'total_employees': len(employees),
            'enrolled_employees': len(set(enrollments.mapped('student_id'))),
            'total_enrollments': len(enrollments),
            'completion_rate': 0,
            'average_score': 0,
            'top_performers': [],
            'skills_gaps': [],
        }
        
        if report['total_enrollments'] > 0:
            completed = enrollments.filtered(lambda e: e.state == 'completed')
            report['completion_rate'] = len(completed) / report['total_enrollments'] * 100
            report['average_score'] = sum(
                e.score for e in completed if e.score
            ) / len([e for e in completed if e.score])
        
        # Get top performers
        student_scores = {}
        for enrollment in enrollments:
            if enrollment.student_id.id not in student_scores:
                student_scores[enrollment.student_id.id] = []
            if enrollment.score:
                student_scores[enrollment.student_id.id].append(enrollment.score)
        
        for student_id, scores in student_scores.items():
            avg_score = sum(scores) / len(scores)
            report['top_performers'].append({
                'student': self.env['res.partner'].browse(student_id).name,
                'average_score': avg_score,
                'courses_completed': len(scores),
            })
        
        report['top_performers'] = sorted(
            report['top_performers'],
            key=lambda x: x['average_score'],
            reverse=True
        )[:5]
        
        return report

class LMSGamification(models.Model):
    _name = 'lms.gamification'
    _description = 'LMS Gamification Engine'
    
    @api.model
    def award_badges(self, student_id, achievement_type, **kwargs):
        """Award badges based on student achievements"""
        student = self.env['res.partner'].browse(student_id)
        
        badge_data = {
            'course_completion': {
                'name': 'Course Master',
                'description': 'Completed a course',
                'image': 'course_completion_badge.png',
            },
            'perfect_score': {
                'name': 'Perfect Score',
                'description': 'Achieved 100% on a quiz',
                'image': 'perfect_score_badge.png',
            },
            'fast_learner': {
                'name': 'Fast Learner',
                'description': 'Completed course in record time',
                'image': 'fast_learner_badge.png',
            },
            'streak': {
                'name': 'Learning Streak',
                'description': 'Completed lessons for 7 consecutive days',
                'image': 'streak_badge.png',
            },
        }
        
        if achievement_type in badge_data:
            badge_info = badge_data[achievement_type]
            # Create badge record or update existing
            badge = self.env['gamification.badge'].search([
                ('name', '=', badge_info['name'])
            ], limit=1)
            
            if not badge:
                badge = self.env['gamification.badge'].create({
                    'name': badge_info['name'],
                    'description': badge_info['description'],
                    'active': True,
                })
            
            # Award badge to student
            self.env['gamification.badge.user'].create({
                'user_id': student.user_id.id,
                'badge_id': badge.id,
                'comment': badge_info['description'],
            })
    
    @api.model
    def update_leaderboard(self, company_id=None):
        """Update learning leaderboard"""
        domain = []
        if company_id:
            domain.append(('company_id', '=', company_id))
        
        enrollments = self.env['lms.enrollment'].search(domain)
        
        leaderboard_data = {}
        for enrollment in enrollments:
            if enrollment.student_id.id not in leaderboard_data:
                leaderboard_data[enrollment.student_id.id] = {
                    'student': enrollment.student_id.name,
                    'points': 0,
                    'courses_completed': 0,
                    'average_score': 0,
                    'badges': 0,
                }
            
            data = leaderboard_data[enrollment.student_id.id]
            data['points'] += enrollment.score or 0
            if enrollment.state == 'completed':
                data['courses_completed'] += 1
        
        # Convert to list and sort by points
        leaderboard = sorted(
            leaderboard_data.values(),
            key=lambda x: x['points'],
            reverse=True
        )
        
        return leaderboard[:10]