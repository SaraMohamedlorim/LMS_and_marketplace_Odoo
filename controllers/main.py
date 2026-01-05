from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website
import json
import base64

class LMSWebsite(Website):
    
    @http.route('/lms/courses', type='http', auth="public", website=True)
    def lms_courses(self, **kwargs):
        domain = [('published', '=', True)]
        
        # Filter by category
        category_id = kwargs.get('category')
        if category_id:
            domain.append(('category_id', '=', int(category_id)))
        
        # Filter by search
        search = kwargs.get('search')
        if search:
            domain.append(('name', 'ilike', search))
        
        # Filter by level
        level = kwargs.get('level')
        if level:
            domain.append(('level', '=', level))
        
        courses = request.env['lms.course'].search(domain)
        
        categories = request.env['lms.category'].search([])
        
        values = {
            'courses': courses,
            'categories': categories,
            'search': search,
            'category_id': int(category_id) if category_id else False,
            'level': level,
        }
        return request.render("lms_marketplace.courses_page", values)
    
    @http.route('/lms/course/<int:course_id>', type='http', auth="public", website=True)
    def lms_course_detail(self, course_id, **kwargs):
        course = request.env['lms.course'].browse(course_id)
        if not course.exists() or not course.published:
            return request.redirect('/lms/courses')
        
        # Check if user is enrolled
        enrollment = None
        if not request.env.user._is_public():
            enrollment = request.env['lms.enrollment'].search([
                ('course_id', '=', course_id),
                ('student_id', '=', request.env.user.partner_id.id)
            ], limit=1)
        
        values = {
            'course': course,
            'enrollment': enrollment,
            'is_enrolled': bool(enrollment),
        }
        return request.render("lms_marketplace.course_detail_page", values)
    
    @http.route('/lms/course/enroll/<int:course_id>', type='http', auth="public", website=True)
    def lms_course_enroll(self, course_id, **kwargs):
        course = request.env['lms.course'].browse(course_id)
        if not course.exists() or not course.published:
            return request.redirect('/lms/courses')
        
        if request.env.user._is_public():
            return request.redirect('/web/login?redirect=/lms/course/%s' % course_id)
        
        # Check if already enrolled
        existing_enrollment = request.env['lms.enrollment'].search([
            ('course_id', '=', course_id),
            ('student_id', '=', request.env.user.partner_id.id)
        ])
        
        if existing_enrollment:
            return request.redirect('/lms/learning/%s' % course_id)
        
        # Create enrollment
        enrollment = request.env['lms.enrollment'].create({
            'student_id': request.env.user.partner_id.id,
            'course_id': course_id,
            'state': 'draft',
        })
        
        if course.is_free:
            enrollment.write({
                'state': 'in_progress',
                'payment_status': 'free'
            })
            return request.redirect('/lms/learning/%s' % course_id)
        else:
            # Redirect to payment
            return request.redirect('/shop/payment')
    
    @http.route('/lms/learning/<int:course_id>', type='http', auth="user", website=True)
    def lms_learning(self, course_id, **kwargs):
        course = request.env['lms.course'].browse(course_id)
        enrollment = request.env['lms.enrollment'].search([
            ('course_id', '=', course_id),
            ('student_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        if not enrollment:
            return request.redirect('/lms/course/%s' % course_id)
        
        # Get current module and content
        current_module_id = kwargs.get('module')
        current_content_id = kwargs.get('content')
        
        values = {
            'course': course,
            'enrollment': enrollment,
            'current_module_id': int(current_module_id) if current_module_id else False,
            'current_content_id': int(current_content_id) if current_content_id else False,
        }
        return request.render("lms_marketplace.learning_page", values)
    
    @http.route('/lms/content/complete', type='json', auth="user", website=True)
    def lms_content_complete(self, content_id, enrollment_id, **kwargs):
        content = request.env['lms.content'].browse(content_id)
        enrollment = request.env['lms.enrollment'].browse(enrollment_id)
        
        # Create or update content progress
        content_progress = request.env['lms.content.progress'].search([
            ('enrollment_id', '=', enrollment_id),
            ('content_id', '=', content_id)
        ], limit=1)
        
        if not content_progress:
            content_progress = request.env['lms.content.progress'].create({
                'enrollment_id': enrollment_id,
                'content_id': content_id,
                'state': 'completed',
            })
        else:
            content_progress.write({'state': 'completed'})
        
        # Check if course is completed
        if enrollment.progress >= 100:
            enrollment.action_complete_course()
        
        return {'success': True, 'progress': enrollment.progress}
    
    @http.route('/lms/quiz/start/<int:quiz_id>', type='http', auth="user", website=True)
    def lms_quiz_start(self, quiz_id, **kwargs):
        quiz = request.env['lms.quiz'].browse(quiz_id)
        enrollment = request.env['lms.enrollment'].search([
            ('course_id', '=', quiz.course_id.id),
            ('student_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        if not enrollment:
            return request.redirect('/lms/courses')
        
        # Generate quiz attempt
        attempt = quiz.action_generate_quiz_attempt(enrollment)
        
        values = {
            'quiz': quiz,
            'attempt': attempt,
            'enrollment': enrollment,
        }
        return request.render("lms_marketplace.quiz_page", values)
    
    @http.route('/lms/quiz/submit', type='json', auth="user", website=True)
    def lms_quiz_submit(self, attempt_id, answers, **kwargs):
        attempt = request.env['lms.quiz.attempt'].browse(attempt_id)
        
        # Update student answers
        for question_id, answer_data in answers.items():
            attempt_question = attempt.questions.filtered(
                lambda q: q.question_id.id == int(question_id)
            )
            if attempt_question:
                if answer_data.get('type') == 'multiple_choice':
                    attempt_question.write({
                        'student_answer_ids': [(6, 0, answer_data.get('answers', []))]
                    })
                elif answer_data.get('type') == 'essay':
                    attempt_question.write({
                        'student_essay_answer': answer_data.get('answer', '')
                    })
        
        # Submit and grade quiz
        attempt.action_submit_quiz()
        
        return {
            'success': True,
            'score': attempt.score,
            'is_passed': attempt.is_passed,
            'redirect_url': '/lms/learning/%s' % attempt.enrollment_id.course_id.id
        }
    
    @http.route('/lms/certificate/<string:verify_hash>', type='http', auth="public", website=True)
    def lms_certificate_verify(self, verify_hash, **kwargs):
        certificate = request.env['lms.certificate'].search([
            ('verification_hash', '=', verify_hash)
        ], limit=1)
        
        if not certificate:
            return request.render("lms_marketplace.certificate_not_found")
        
        values = {
            'certificate': certificate,
        }
        return request.render("lms_marketplace.certificate_verify_page", values)
    
    @http.route('/lms/instructor/apply', type='http', auth="user", website=True)
    def lms_instructor_apply(self, **kwargs):
        partner = request.env.user.partner_id
        instructor = request.env['lms.instructor'].search([
            ('partner_id', '=', partner.id)
        ], limit=1)
        
        if instructor:
            return request.redirect('/lms/instructor/dashboard')
        
        if request.httprequest.method == 'POST':
            # Create instructor application
            instructor = request.env['lms.instructor'].create({
                'partner_id': partner.id,
                'bio': request.params.get('bio'),
                'expertise': [(6, 0, request.params.get('expertise_ids', []))],
            })
            return request.redirect('/lms/instructor/dashboard')
        
        tags = request.env['lms.tag'].search([])
        values = {
            'tags': tags,
        }
        return request.render("lms_marketplace.instructor_application_page", values)
    
    @http.route('/lms/instructor/dashboard', type='http', auth="user", website=True)
    def lms_instructor_dashboard(self, **kwargs):
        instructor = request.env['lms.instructor'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        if not instructor:
            return request.redirect('/lms/instructor/apply')
        
        courses = request.env['lms.course'].search([
            ('instructor_id', '=', instructor.id)
        ])
        
        values = {
            'instructor': instructor,
            'courses': courses,
        }
        return request.render("lms_marketplace.instructor_dashboard_page", values)