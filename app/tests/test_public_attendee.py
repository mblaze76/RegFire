import os,json,uuid
from unittest.mock import patch
from urllib.error import HTTPError
from test_checkout import CheckoutStorage

class PublicAttendeeTests(CheckoutStorage):
    def setUp(self):
        import attendee_accounts
        attendee_accounts._attempts.clear()
        super().setUp()
        self.flow,self.page,self.data=self.setup_order(0)
        self.flags=patch.dict(os.environ,REGFIRE_STAGING_FLOW_IDS=self.flow);self.flags.start()
        self.attendee_cookie='';self.attendee_csrf=''
    def tearDown(self):
        self.flags.stop();super().tearDown()
    def public(self,path,data=None,method=None):
        from urllib.request import Request,build_opener,ProxyHandler
        headers={'Origin':self.url,'Content-Type':'application/json'}
        if self.attendee_cookie:headers['Cookie']=self.attendee_cookie
        if self.attendee_csrf:headers['X-Attendee-CSRF']=self.attendee_csrf
        req=Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
        with build_opener(ProxyHandler({})).open(req) as response:
            cookie=response.headers.get('Set-Cookie')
            if cookie:self.attendee_cookie=cookie.split(';')[0]
            return json.load(response)
    def signup(self,address='test-attendee@example.test'):
        result=self.public('/api/public/events/'+self.flow+'/attendee-account',dict(email=address,password='Synthetic-password-12345',confirm_password='Synthetic-password-12345'))
        self.attendee_csrf=self.public('/api/attendee/me')['user']['csrf']
        return result
    def test_public_account_group_checkout_and_confirmation(self):
        token=self.signup()['enrollment_token']
        data=self.data|dict(enrollment_token=token,contacts=self.data['contacts']|{'email':'test-attendee@example.test'})
        colleague=self.data|dict(contacts=self.data['contacts']|{'email':'colleague@example.test'})
        order=self.public('/api/public/events/'+self.flow+'/checkout/group-save',dict(request_key=str(uuid.uuid4()),members=[data,colleague]))
        done=self.public('/api/public/checkout/'+order['id']+'/start',{})
        self.assertEqual(done['status'],'confirmed_free')
        for ident in order['group_order_ids']:
            self.assertEqual(self.public('/api/public/checkout/'+ident+'/confirmation')['confirmation_id'],ident)
        self.assertEqual(len(self.public('/api/attendee/registrations')['registrations']),1)
    def test_other_attendee_cannot_access_order(self):
        self.signup();order=self.public('/api/public/events/'+self.flow+'/checkout/save',self.data)
        self.signup('other@example.test')
        with self.assertRaises(HTTPError) as error:self.public('/api/public/checkout/'+order['id']+'/status')
        self.assertEqual(error.exception.code,404)
    def test_public_cannot_edit_or_read_organizer_or_other_flow(self):
        self.signup()
        for path,method in [('/api/events','GET'),('/api/admin/users','GET'),('/api/public/events/'+self.flow+'/registration-page','PUT'),('/api/public/events/'+str(uuid.uuid4())+'/flow-preview','GET')]:
            with self.subTest(path=path),self.assertRaises(HTTPError):self.public(path,{} if method=='PUT' else None,method)
    def test_existing_account_password_cannot_be_replaced(self):
        self.signup()
        with self.assertRaises(HTTPError):self.public('/api/public/events/'+self.flow+'/attendee-account',dict(email='test-attendee@example.test',password='Different-password-12345',confirm_password='Different-password-12345'))
        self.signup()
    def test_save_requires_attendee_and_csrf(self):
        with self.assertRaises(HTTPError):self.public('/api/public/events/'+self.flow+'/checkout/save',self.data)
        self.signup();self.attendee_csrf='wrong'
        with self.assertRaises(HTTPError) as error:self.public('/api/public/events/'+self.flow+'/checkout/save',self.data)
        self.assertEqual(error.exception.code,403)
    def test_public_preview_does_not_reveal_organizer_contact(self):
        result=self.public('/api/public/events/'+self.flow+'/flow-preview')
        self.assertNotIn('email',result['event']);self.assertNotIn('organizer',result['event'])
    def test_guest_cannot_upload_or_override_saved_prices(self):
        with self.assertRaises(HTTPError):self.public('/api/public/events/'+self.flow+'/assets/logo',{})
        forged=self.page|dict(currency='EUR',regtypes=[])
        result=self.public('/api/public/events/'+self.flow+'/pricing-preview',dict(page=forged,at='1900-01-01'))
        self.assertIn('attendee',result['regtypes'])
        self.assertEqual(result['regtypes']['attendee']['price_minor'],0)
    def test_public_confirmation_pdf_and_disabled_flow(self):
        self.signup();order=self.public('/api/public/events/'+self.flow+'/checkout/save',self.data)
        self.public('/api/public/checkout/'+order['id']+'/start',{})
        with patch.dict(os.environ,REGFIRE_STAGING_FLOW_IDS=''):
            with self.assertRaises(HTTPError) as error:self.public('/api/public/checkout/'+order['id']+'/confirmation')
            self.assertEqual(error.exception.code,404)
