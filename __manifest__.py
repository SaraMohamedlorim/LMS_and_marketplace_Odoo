{
    'name': 'LMS Marketplace',
    'version': '0.0.1',
    'category': 'Education',
    'summary': 'Comprehensive Learning Management System with Marketplace',
    'description': """
        Transform Odoo into a full-featured LMS and Course Marketplace
        with courses, modules, videos, quizzes, certificates, payments,
        and advanced analytics.
    """,
    'author': 'Sara Mohammed ',
    'website': 'https://www.learning.com',
    'depends': [
        'base', 
        'web', 
        'website', 
        'website_sale', 
        'payment', 
        'gamification',
        'hr',
        'account',
    ],
      'images': [
        'static/description/learning.png',
    ],

    'icon': '/LMS_and_marketplace/static/description/learning.png',
    'data': [
         # Security files first
        'security/lms_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        

         # Main data and menus
        # 'data/lms_data.xml',
        # 'data/achievement_data.xml',
        # 'data/certificate_data.xml',
        # 'data/gamification_data.xml',
        # 'data/compliance_rules.xml',
        # 'data/payment_gateways.xml',
        

         # Partner and User related views
        'views/lms_partner_views.xml',


        # Course structure views
        'views/lms_course_views.xml',
        'views/lms_module_views.xml',
        'views/lms_content_views.xml',
        # 'views/lms_category_views.xml',
        # 'views/lms_tag_views.xml',

        
        # Enrollment and progress views
        'views/lms_enrollment_views.xml',
        # 'views/lms_content_progress_views.xml',

        # Quiz and assessment views
        'views/lms_quiz_views.xml',
        # 'views/lms_question_views.xml',
        # 'views/lms_quiz_attempt_views.xml',


         # Certificate and achievement views
        'views/lms_certificate_views.xml',
        # 'views/lms_certificate_template_views.xml',
        'views/lms_achievement_views.xml',


        # Live session views
        'views/lms_live_session_views.xml',
        'views/lms_live_session_attendance_views.xml',


        # Marketplace views
        'views/lms_marketplace_views.xml',
        # 'views/lms_payout_views.xml',
        # 'views/lms_instructor_profile_views.xml',

        # Corporate views
        'views/lms_corporate_views.xml',
        'views/lms_compliance_rule_views.xml',
        'views/lms_subscription_views.xml',

        # Payment views
       'views/lms_payment_views.xml',
    #    'views/lms_payment_gateway_views.xml',

       
        
       
        # Advanced features views
        'views/lms_advanced_views.xml',
        # 'views/lms_scorm_integration_views.xml',
        # 'views/lms_zoom_integration_views.xml',
        # 'views/lms_adaptive_learning_views.xml',
        # 'views/lms_proctoring_views.xml',
        # 'views/lms_gamification_views.xml',

       
      # Analytics and reports
        'views/lms_analytics_views.xml',
        'views/lms_dashboard_views.xml',
        'views/lms_report_views.xml',
            

       # Settings and configuration
        'views/lms_settings_views.xml',
        'views/lms_configuration_views.xml',


        # 'reports/lms_reports.xml',
        # 'reports/lms_certificate_report.xml',
        # 'reports/lms_analytics_report.xml',
    

         # Website views (if applicable)
        # 'views/website_lms_templates.xml',
        # 'views/website_lms_course_pages.xml',
        # 'views/website_lms_profile_pages.xml',
        
        
        
        

        # Wizard views
        'wizards/lms_bulk_enrollment_wizard_views.xml',
        'wizards/lms_certificate_generation_wizard_views.xml',
        # 'wizards/lms_report_generation_wizard_views.xml',
        # 'wizards/lms_payment_wizard_views.xml',
            
        'views/lms_menus.xml',

       
        
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'lms_marketplace/static/src/js/lms_dashboard.js',
    #         'lms_marketplace/static/src/css/lms_backend.css',
    #     ],
    #     'website.assets_wysiwyg': [
    #         'lms_marketplace/static/src/js/lms_website.js',
    #     ],
    #     'web.assets_frontend': [
    #         'lms_marketplace/static/src/js/lms_player.js',
    #         'lms_marketplace/static/src/js/lms_quiz.js',
    #         'lms_marketplace/static/src/css/lms_frontend.css',
    #     ],
    # },
    'demo': [
        'data/lms_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}