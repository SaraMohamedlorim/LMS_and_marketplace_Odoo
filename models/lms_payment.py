from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class LMSPaymentIntegration(models.Model):
    _name = 'lms.payment.integration'
    _description = 'LMS Payment Gateway Integration'
    
    @api.model
    def process_payment(self, enrollment_id, payment_method_id=None):
        """Process payment for course enrollment"""
        enrollment = self.env['lms.enrollment'].browse(enrollment_id)
        course = enrollment.course_id
        
        if course.is_free:
            enrollment.write({
                'payment_status': 'free',
                'state': 'in_progress'
            })
            return {'success': True, 'message': 'Free enrollment processed'}
        
        # Get payment gateway configuration
        payment_gateway = self.env['ir.config_parameter'].sudo().get_param(
            'lms_payment_gateway', 'odoo'
        )
        
        if payment_gateway == 'stripe':
            return self._process_stripe_payment(enrollment, payment_method_id)
        elif payment_gateway == 'paypal':
            return self._process_paypal_payment(enrollment)
        elif payment_gateway == 'odoo':
            return self._process_odoo_payment(enrollment)
        else:
            raise UserError(_("Payment gateway not configured"))
    
    def _process_stripe_payment(self, enrollment, payment_method_id):
        """Process payment using Stripe"""
        # Check if Stripe is available
        try:
            import stripe
        except ImportError:
            # Fallback to Odoo payment
            return self._process_odoo_payment(enrollment)
        
        stripe_api_key = self.env['ir.config_parameter'].sudo().get_param(
            'lms_stripe_secret_key'
        )
        
        if not stripe_api_key:
            raise UserError(_("Stripe API key not configured"))
        
        stripe.api_key = stripe_api_key
        
        try:
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(enrollment.course_id.price * 100),  # Convert to cents
                currency=enrollment.course_id.currency_id.name.lower(),
                payment_method=payment_method_id,
                confirmation_method='manual',
                confirm=True,
                return_url=f"{self.get_base_url()}/lms/payment/success",
            )
            
            # Create invoice record
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': enrollment.student_id.id,
                'invoice_line_ids': [(0, 0, {
                    'name': enrollment.course_id.name,
                    'quantity': 1,
                    'price_unit': enrollment.course_id.price,
                })],
            })
            
            enrollment.write({
                'payment_status': 'paid',
                'state': 'in_progress',
                'invoice_id': invoice.id,
            })
            
            # Process instructor payout share
            self._process_instructor_payout(enrollment)
            
            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
            }
            
        except Exception as e:
            # Fallback to Odoo payment if Stripe fails
            return self._process_odoo_payment(enrollment)
    
    def _process_odoo_payment(self, enrollment):
        """Process payment using Odoo's built-in payment system"""
        # Create sale order
        order = self.env['sale.order'].create({
            'partner_id': enrollment.student_id.id,
            'order_line': [(0, 0, {
                'product_id': self._get_lms_product_id(),
                'name': enrollment.course_id.name,
                'product_uom_qty': 1,
                'price_unit': enrollment.course_id.price,
            })],
        })
        
        # Confirm the order
        order.action_confirm()
        
        # Create invoice
        invoice = order._create_invoices()
        invoice.action_post()
        
        enrollment.write({
            'payment_status': 'paid',
            'state': 'in_progress',
            'invoice_id': invoice.id,
        })
        
        # Process instructor payout share
        self._process_instructor_payout(enrollment)
        
        return {
            'success': True,
            'message': 'Payment processed via Odoo',
            'invoice_id': invoice.id,
        }
    
    def _get_lms_product_id(self):
        """Get or create LMS product for sales"""
        product = self.env['product.product'].search([
            ('default_code', '=', 'LMS_COURSE')
        ], limit=1)
        
        if not product:
            product = self.env['product.product'].create({
                'name': 'LMS Course',
                'default_code': 'LMS_COURSE',
                'type': 'service',
                'invoice_policy': 'order',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 0.0,  # Price will be set per course
            })
        
        return product.id
    
    def _process_instructor_payout(self, enrollment):
        """Process revenue sharing with instructor"""
        revenue_share = float(self.env['ir.config_parameter'].sudo().get_param(
            'lms_marketplace.revenue_share_percentage', 30.0
        ))
        
        instructor_share = (100 - revenue_share) / 100
        instructor_amount = enrollment.course_id.price * instructor_share
        
        # Create payout record
        self.env['lms.payout'].create({
            'instructor_id': enrollment.course_id.instructor_id.id,
            'amount': instructor_amount,
            'currency_id': enrollment.course_id.currency_id.id,
            'enrollment_id': enrollment.id,
            'status': 'pending',
            'payout_method': enrollment.course_id.instructor_id.payout_method or 'bank_transfer',
        })
    
    def _process_paypal_payment(self, enrollment):
        """Process payment using PayPal"""
        # PayPal integration placeholder
        # In production, implement actual PayPal API integration
        raise UserError(_("PayPal integration is not yet implemented. Please use Odoo payment gateway."))
    
    @api.model
    def handle_refund(self, enrollment_id, reason=None):
        """Process refund for enrollment"""
        enrollment = self.env['lms.enrollment'].browse(enrollment_id)
        
        if enrollment.payment_status != 'paid':
            raise UserError(_("Only paid enrollments can be refunded"))
        
        # Create credit note for invoice
        if enrollment.invoice_id:
            reversal_wizard = self.env['account.move.reversal'].create({
                'move_ids': [(6, 0, [enrollment.invoice_id.id])],
                'reason': reason or 'LMS Enrollment Refund',
                'refund_method': 'refund',
            })
            reversal_wizard.reverse_moves()
        
        enrollment.write({
            'payment_status': 'refunded',
            'state': 'cancelled',
        })
        
        return {'success': True, 'message': 'Refund processed successfully'}

class LMSSubscription(models.Model):
    _name = 'lms.subscription'
    _description = 'LMS Corporate Subscriptions'
    
    @api.model
    def create_corporate_subscription(self, company_id, plan_type, seats, duration_months):
        """Create corporate subscription plan"""
        company = self.env['res.company'].browse(company_id)
        
        subscription = self.env['lms.corporate.subscription'].create({
            'company_id': company_id,
            'plan_type': plan_type,
            'total_seats': seats,
            'used_seats': 0,
            'duration_months': duration_months,
            'start_date': fields.Datetime.now(),
            'end_date': fields.Datetime.now() + timedelta(days=duration_months * 30),
            'status': 'active',
        })
        
        # Create invoice for subscription
        self._create_subscription_invoice(subscription)
        
        return subscription
    
    def _create_subscription_invoice(self, subscription):
        """Create invoice for corporate subscription"""
        plan_pricing = {
            'basic': 50,  # per seat per month
            'professional': 100,
            'enterprise': 200,
        }
        
        monthly_price = plan_pricing.get(subscription.plan_type, 50)
        total_amount = monthly_price * subscription.total_seats * subscription.duration_months
        
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': subscription.company_id.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': f"LMS {subscription.plan_type.title()} Subscription - {subscription.duration_months} months",
                'quantity': subscription.total_seats,
                'price_unit': monthly_price * subscription.duration_months,
            })],
        })
        
        subscription.write({'invoice_id': invoice.id})
        
        return invoice
    
    @api.model
    def check_subscription_access(self, company_id, course_id):
        """Check if company subscription allows access to course"""
        subscription = self.env['lms.corporate.subscription'].search([
            ('company_id', '=', company_id),
            ('status', '=', 'active'),
            ('end_date', '>=', fields.Datetime.now()),
        ], order='create_date desc', limit=1)
        
        if not subscription:
            return False
        
        # Check if there are available seats
        if subscription.used_seats >= subscription.total_seats:
            return False
        
        # Check if course is included in subscription plan
        course = self.env['lms.course'].browse(course_id)
        if subscription.plan_type == 'basic' and course.level == 'advanced':
            return False  # Advanced courses not included in basic plan
        
        return True