import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from demographics import validate,evaluate
TYPES=[{'id':'attendee','name':'Attendee'},{'id':'speaker','name':'Speaker'},{'id':'staff','name':'Staff'}]
def question(id,kind='text',options=None,rules=None,visible=None,required=False,mode='all'):
 return dict(id=id,label=id,help='',type=kind,required=required,options=[dict(id=x,label=x) for x in (options or [])],visible_to=visible,conditions=dict(mode=mode,rules=rules or []))
def rule(q,value,op='equals'):return dict(question_id=q,operator=op,value=value)
def page(questions):return dict(title='Custom questions',intro='',questions=questions)
def sample():return page([question('path','radio',['workshops','networking']),question('topics','multiselect',['technology','design'],[rule('path','workshops')]),question('details',rules=[rule('topics','technology','includes')],required=True)])

class DemographicsTests(unittest.TestCase):
 def test_nested_hidden_answers_do_not_drive_branches(self):
  data=sample();answers={'path':'workshops','topics':['technology'],'details':'A topic'}
  self.assertEqual(evaluate(data,TYPES,'attendee',answers,True)['visible_ids'],['path','topics','details'])
  answers['path']='networking';result=evaluate(data,TYPES,'attendee',answers,True)
  self.assertEqual(result['visible_ids'],['path']);self.assertEqual(result['effective_answers'],{'path':'networking'});self.assertEqual(result['errors'],{})
 def test_regtype_assignment_shared_all_and_hidden_parent(self):
  data=sample();data['questions'][0]['visible_to']=['attendee','speaker']
  answers={'path':'workshops','topics':['technology']}
  for rt in ('attendee','speaker'):
   result=evaluate(data,TYPES,rt,answers,True);self.assertIn('details',result['visible_ids']);self.assertIn('details',result['errors'])
  result=evaluate(data,TYPES,'staff',answers,True)
  self.assertEqual(result['visible_ids'],[]);self.assertEqual(result['errors'],{});self.assertEqual(result['effective_answers'],{})
 def test_all_any_single_multi_and_unanswered_negative(self):
  data=page([question('single','select',['a','b']),question('multiple','multiselect',['x','y']),question('follow',rules=[rule('single','a'),rule('multiple','x','includes')],mode='all')])
  self.assertNotIn('follow',evaluate(data,TYPES,'attendee',{'single':'a'})['visible_ids'])
  data['questions'][2]['conditions']['mode']='any';self.assertIn('follow',evaluate(data,TYPES,'attendee',{'single':'a'})['visible_ids'])
  data['questions'][2]['conditions']['rules']=[rule('single','b','not_equals')]
  self.assertNotIn('follow',evaluate(data,TYPES,'attendee',{})['visible_ids'])
 def test_cycles_forward_missing_options_and_regtypes_rejected(self):
  data=sample();mutations=[]
  bad=copy.deepcopy(data);bad['questions'][0]['conditions']['rules']=[rule('details','yes')];mutations.append(bad)
  bad=copy.deepcopy(data);bad['questions'][1]['conditions']['rules']=[rule('missing','yes')];mutations.append(bad)
  bad=copy.deepcopy(data);bad['questions'][0]['options']=[dict(id='new',label='New'),dict(id='other',label='Other')];mutations.append(bad)
  bad=copy.deepcopy(data);bad['questions'][0]['visible_to']=['deleted'];mutations.append(bad)
  bad=copy.deepcopy(data);bad['questions'].reverse();mutations.append(bad)
  for invalid in mutations:
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate(invalid,TYPES)
 def test_option_rename_keeps_stable_branch_reference(self):
  data=sample();data['questions'][0]['options'][0]['label']='Renamed workshop'
  self.assertIn('topics',evaluate(data,TYPES,'speaker',{'path':'workshops'})['visible_ids'])
 def test_type_comparisons_and_required_answer_validation(self):
  data=page([question('num','number'),question('day','date'),question('yes','boolean'),question('follow',rules=[rule('num','10','gte'),rule('day','2026-10-01','gte'),rule('yes',False)],required=True)])
  result=evaluate(data,TYPES,'attendee',{'num':'10.0','day':'2026-10-01','yes':False},True)
  self.assertIn('follow',result['visible_ids']);self.assertIn('follow',result['errors'])
  self.assertIn('num',evaluate(data,TYPES,'attendee',{'num':'NaN'},True)['errors'])
  with self.assertRaises(ValueError):evaluate(data,TYPES,[],{})
