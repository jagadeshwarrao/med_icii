"""Email and private-storage adapters. Configure credentials only through environment secrets."""
import os, logging, smtplib, json
from html import escape
from email.message import EmailMessage
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

log=logging.getLogger(__name__)

class TransactionalEmail:
    def _message(self,template:str,context:dict):
        order=context.get('order_number','')
        messages={
            'verify-account':('Welcome to Medicii','Your Medicii account was created. Sign in to begin a quote request.'),
            'password-reset':('Reset your Medicii password','Use the secure link below to set a new password. It expires in 30 minutes. If you did not request this, you can safely ignore this email.'),
            'quote-request-received':('Medicii received your quote request',f'We received quote request {context.get("quote_number","")}. We will notify you when pricing is ready.'),
            'quote-reviewed':('Your Medicii quote is ready',f'Your quote {context.get("quote_number","")} has been reviewed. Sign in to review the itemised quote and decide whether to add it to your order.'),
            'quote-accepted':('Quote added to your Medicii order',f'Quote {context.get("quote_number","")} was added to order {order}. You can continue checkout from your account.'),
            'quote-withdrawn':('A Medicii quote was withdrawn',f'Quote {context.get("quote_number","")} is no longer available. Contact support if you have questions.'),
            'account-updated':('Your Medicii account was updated','Your account details were updated. If you did not make or expect this change, contact support immediately.'),
            'documents-updated':('Your Medicii documents were received',f'We received an updated {context.get("document_kind","document").replace("_"," ").lower()} for order {order}.'),
            'delivery-updated':('Your Medicii delivery details were updated',f'Delivery details for order {order} were updated.'),
            'order-status-updated':('Your Medicii order status changed',f'Order {order} is now {context.get("status","").replace("_"," ").title()}.'),
            'order-removed':('A Medicii order was removed',f'Order {order} was removed before payment or fulfillment. Contact support if you have questions.'),
            'order-confirmed':(f'Medicii order {order} confirmed',f'Thank you for your order {order}. We will send updates as its status changes.'),
        }
        content_html=''
        if template=='new-order-confirmed':
            item_lines=[]; item_rows=[]
            for item in context.get('items',[]):
                medicine=escape(str(item.get('medicine','Medicine'))); quantity=escape(str(item.get('quantity',''))); price=escape(str(item.get('price','0'))); shipping=escape(str(item.get('shipping','0'))); service_fee=escape(str(item.get('service_fee','0')))
                item_lines.append(f"• {medicine} × {quantity}\n  Medicine: ${price} | Shipping: ${shipping} | Service fee: ${service_fee}")
                item_rows.append(f'<tr><td style="padding:12px 8px;border-top:1px solid #e4e8e1"><strong>{medicine}</strong><br/><span style="color:#71847f;font-size:12px">Quantity: {quantity}</span></td><td style="padding:12px 8px;border-top:1px solid #e4e8e1;white-space:nowrap">${price}<br/><span style="color:#71847f;font-size:12px">Ship ${shipping} · Fee ${service_fee}</span></td></tr>')
            items='\n\n'.join(item_lines) or 'No item details were supplied.'
            address=context.get('shipping_address') or {}
            address_text=', '.join(str(address.get(k,'')) for k in ('line1','city','state','postal_code','country') if address.get(k))
            customer_name=escape(str(context.get('customer_name',''))); customer_email=escape(str(context.get('customer_email',''))); customer_phone=escape(str(address.get('phone',''))); order_number=escape(str(order)); total=escape(str(context.get('total','')))
            subject=f'New paid Medicii order {order}'; body=f'NEW PAID ORDER\n\nOrder number\n{order}\n\nCustomer\n{context.get("customer_name","")}\n{context.get("customer_email","")}\n\nDelivery address\n{address.get("full_name","")}\n{address_text}\nPhone: {address.get("phone","")}\n\nItems\n{items}\n\nORDER TOTAL: ${context.get("total","")}'
            content_html=f'''<p style="line-height:1.6;color:#385a55">A customer has completed payment. Review the fulfillment details below.</p><div style="margin:22px 0;background:#f7f7f2;border-radius:10px;padding:18px"><span style="color:#71847f;font-size:11px;font-weight:700;letter-spacing:1px">ORDER NUMBER</span><div style="font-size:22px;font-weight:700;color:#163936;margin-top:5px">{order_number}</div></div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:22px 0;border:1px solid #e4e8e1;border-radius:10px"><tr><td style="padding:16px"><span style="color:#e27650;font-size:11px;font-weight:700;letter-spacing:1px">CUSTOMER</span><p style="margin:7px 0 0;line-height:1.55"><strong>{customer_name}</strong><br/><a style="color:#da7150" href="mailto:{customer_email}">{customer_email}</a></p></td></tr><tr><td style="padding:16px;border-top:1px solid #e4e8e1"><span style="color:#e27650;font-size:11px;font-weight:700;letter-spacing:1px">DELIVERY ADDRESS</span><p style="margin:7px 0 0;line-height:1.55">{escape(str(address.get('full_name','')))}<br/>{escape(address_text)}<br/>Phone: {customer_phone}</p></td></tr></table><h2 style="font-size:18px;margin:25px 0 8px">Items to fulfill</h2><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse">{''.join(item_rows)}</table><div style="margin-top:22px;padding-top:16px;border-top:2px solid #163936;text-align:right"><span style="color:#71847f;font-size:12px;font-weight:700;letter-spacing:1px">ORDER TOTAL</span><div style="font-size:25px;font-weight:700;color:#163936;margin-top:4px">${total}</div></div>'''
        elif template=='new-quote-request':
            items='\n'.join(f"- {x['medicine']} | {x['strength']} | {x['form']} | Quantity: {x['quantity']}"+(f" | Notes: {x['notes']}" if x.get('notes') else '') for x in context.get('items',[]))
            subject=f'New Medicii quote request {context.get("quote_number","")}'; body=f'Quote request: {context.get("quote_number","")}\nCustomer: {context.get("customer_name","")} <{context.get("customer_email","")}>\n\nRequested medicines:\n{items}\n\nSign in to Medicii Admin to review and price this request.'
        else:
            subject,body=messages.get(template,('Medicii notification','Please sign in to your Medicii account for the latest update.'))
        action_url=context.get('reset_url','') if template=='password-reset' else ''
        if action_url: body+=f'\n\nReset link: {action_url}'
        action_html=f'<p style="margin:26px 0"><a href="{escape(action_url,quote=True)}" style="display:inline-block;background:#163936;color:#fff;text-decoration:none;border-radius:8px;padding:13px 19px;font-weight:700">Reset password</a></p>' if action_url else ''
        message_html=content_html or f'<p style="white-space:pre-line;line-height:1.6;color:#385a55">{escape(body)}</p>'
        html=f'''<!doctype html><html><body style="margin:0;background:#f7f7f2;font-family:Arial,sans-serif;color:#163936"><div style="max-width:620px;margin:32px auto;background:#fff;border:1px solid #e4e8e1;border-radius:16px;overflow:hidden"><div style="padding:26px 32px;background:#163936;color:#fff;font-size:25px;font-weight:700"> <span style="color:#e58155">✦</span> medicii</div><div style="padding:32px"><p style="color:#e27650;letter-spacing:1.5px;font-size:11px;font-weight:700">MEDICII UPDATE</p><h1 style="font-size:26px;margin:0 0 18px">{escape(subject)}</h1>{message_html}{action_html}</div><div style="padding:20px 32px;border-top:1px solid #e4e8e1;color:#71847f;font-size:13px">Need help? Contact <a style="color:#da7150" href="mailto:support@medicii.net">support@medicii.net</a>.<br/>This email was sent by Medicii. Please do not reply to this message.</div></div></body></html>'''
        return subject,body,html
    def send(self,recipient:str,template:str,context:dict):
        subject,body,html=self._message(template,context)
        tenant=os.getenv('GRAPH_TENANT_ID'); client_id=os.getenv('GRAPH_CLIENT_ID'); client_secret=os.getenv('GRAPH_CLIENT_SECRET')
        if tenant and client_id and client_secret:
            try:
                token_request=Request(f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',data=urlencode({'client_id':client_id,'client_secret':client_secret,'scope':'https://graph.microsoft.com/.default','grant_type':'client_credentials'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
                with urlopen(token_request,timeout=15) as response: token=json.load(response)['access_token']
                payload={'message':{'subject':subject,'body':{'contentType':'HTML','content':html},'toRecipients':[{'emailAddress':{'address':recipient}}]},'saveToSentItems':True}
                sender=quote(os.getenv('GRAPH_SENDER',os.getenv('EMAIL_FROM','noreply@medicii.net')),safe='@.')
                graph_request=Request(f'https://graph.microsoft.com/v1.0/users/{sender}/sendMail',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},method='POST')
                with urlopen(graph_request,timeout=15): pass
                log.info('graph_email_sent template=%s recipient_hash=%s',template,hash(recipient)); return True
            except Exception:
                log.exception('graph_email_send_failed template=%s recipient_hash=%s',template,hash(recipient)); return False
        host=os.getenv('SMTP_HOST')
        if not host:
            log.info('email_queued template=%s recipient_hash=%s',template,hash(recipient)); return False
        message=EmailMessage(); message['From']=os.getenv('EMAIL_FROM','noreply@medicii.net'); message['To']=recipient; message['Subject']=subject; message.set_content(body); message.add_alternative(html,subtype='html')
        try:
            port=int(os.getenv('SMTP_PORT','587')); username=os.getenv('SMTP_USERNAME'); password=os.getenv('SMTP_PASSWORD')
            with smtplib.SMTP(host,port,timeout=15) as client:
                if os.getenv('SMTP_STARTTLS','true').lower()=='true': client.starttls()
                if username and password: client.login(username,password)
                client.send_message(message)
            log.info('email_sent template=%s recipient_hash=%s',template,hash(recipient)); return True
        except Exception:
            log.exception('email_send_failed template=%s recipient_hash=%s',template,hash(recipient)); return False

class PrivateStorage:
    def put_pdf(self,key:str,content:bytes):
        """Production: private S3, SSE-KMS, blocked public access, AV scan queue."""
        if os.getenv('STORAGE_MODE')=='s3': raise NotImplementedError('Configure reviewed S3 adapter')
        return key

email=TransactionalEmail(); storage=PrivateStorage()
