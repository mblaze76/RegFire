"""Event-scoped custom questions and an ephemeral branching preview."""
import re
from decimal import Decimal,InvalidOperation
from datetime import date
from registration import text,identity

TYPES={'text','textarea','radio','multiselect','select','number','date','boolean'}
CHOICES={'radio','multiselect','select'}
OPERATORS={
 'text':{'equals','not_equals','contains','is_answered'},
 'textarea':{'equals','not_equals','contains','is_answered'},
 'radio':{'equals','not_equals','is_answered'},'select':{'equals','not_equals','is_answered'},
 'multiselect':{'includes','not_includes','is_answered'},
 'number':{'equals','not_equals','gt','gte','lt','lte','is_answered'},
 'date':{'equals','not_equals','gt','gte','lt','lte','is_answered'},
 'boolean':{'equals','not_equals','is_answered'},
}


def starter(event_id):return dict(event_id=event_id,title='Demographics',intro='',questions=[],status='draft',updated=None)

def decimal(value):
    if not isinstance(value,str) or len(value)>100:raise ValueError('Number values must be numeric text of at most 100 characters.')
    try:
        number=Decimal(value)
        if not number.is_finite() or abs(number)>Decimal('1e15'):raise ValueError()
        return number
    except (ValueError,InvalidOperation):raise ValueError('Enter a finite number between -1e15 and 1e15.')

def answer(question,value):
    kind=question['type']
    if value is None or value=='' or (isinstance(value,list) and not value):return None
    if kind=='boolean':
        if type(value) is not bool:raise ValueError('Choose Yes or No.')
        return value
    if kind=='number':decimal(value);return value.strip()
    if kind=='date':
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Use a valid date in YYYY-MM-DD format.')
        try:date.fromisoformat(value)
        except ValueError:raise ValueError('Use a valid date in YYYY-MM-DD format.')
        return value
    if kind in CHOICES:
        allowed={o['id'] for o in question['options']}
        if kind=='multiselect':
            if not isinstance(value,list) or len(value)>30 or any(not isinstance(v,str) or v not in allowed for v in value) or len(set(value))!=len(value):raise ValueError('Choose valid, distinct options.')
            return value
        if not isinstance(value,str) or value not in allowed:raise ValueError('Choose a valid option.')
        return value
    result=text(value,'Answer',5000)
    return result or None


def validate(data,regtypes):
    if not isinstance(data,dict):raise ValueError('A demographics page is required.')
    result=dict(title=text(data.get('title'),'Page title',200,True),intro=text(data.get('intro',''),'Introduction',5000),questions=[])
    questions=data.get('questions')
    if not isinstance(questions,list) or len(questions)>50:raise ValueError('Use up to 50 demographic questions.')
    allowed_types={r['id'] for r in regtypes};seen=set();earlier={}
    for index,q in enumerate(questions,1):
        if not isinstance(q,dict):raise ValueError('Each question must be an object.')
        qid=identity(q.get('id'),seen,'Question');label=text(q.get('label'),f'Question {index} label',160,True)
        kind=q.get('type')
        if not isinstance(kind,str) or kind not in TYPES:raise ValueError('Choose a supported question type.')
        required=q.get('required')
        if type(required) is not bool:raise ValueError('Question required setting must be true or false.')
        options=q.get('options',[]);normalized=[];option_ids=set();option_labels=set()
        if not isinstance(options,list):raise ValueError('Question options must be a list.')
        if kind in CHOICES:
            if not 2<=len(options)<=30:raise ValueError(f'{label} needs 2–30 choices.')
            for option in options:
                if not isinstance(option,dict):raise ValueError('Each option needs an ID and label.')
                oid=identity(option.get('id'),option_ids,'Option');olabel=text(option.get('label'),'Option label',120,True)
                if olabel.casefold() in option_labels:raise ValueError('Option labels must be distinct.')
                option_labels.add(olabel.casefold());normalized.append(dict(id=oid,label=olabel))
        visible=q.get('visible_to')
        if visible is not None:
            if not isinstance(visible,list) or not visible or any(not isinstance(t,str) or t not in allowed_types for t in visible) or len(set(visible))!=len(visible):raise ValueError(f'{label} references a missing/duplicate RegType. Update its visibility in Demographics.')
        conditions=q.get('conditions',dict(mode='all',rules=[]))
        if not isinstance(conditions,dict) or conditions.get('mode') not in ('all','any'):raise ValueError('Choose all or any branching rules.')
        rules=conditions.get('rules')
        if not isinstance(rules,list) or len(rules)>10:raise ValueError('Use at most 10 branching rules per question.')
        normalized_rules=[]
        for rule in rules:
            if not isinstance(rule,dict):raise ValueError('Each branching rule must be an object.')
            parent=earlier.get(rule.get('question_id')) if isinstance(rule.get('question_id'),str) else None
            if not parent:raise ValueError(f'{label} must branch only from an earlier existing question. Move the source earlier or remove the rule.')
            operator=rule.get('operator')
            if not isinstance(operator,str) or operator not in OPERATORS[parent['type']]:raise ValueError(f'{label} has an operator incompatible with its source question.')
            value=rule.get('value')
            if operator=='is_answered':value=None
            elif parent['type']=='multiselect':
                if not isinstance(value,str) or value not in {o['id'] for o in parent['options']}:raise ValueError(f'{label} references a removed choice.')
            else:
                value=answer(parent,value)
                if value is None:raise ValueError(f'{label} needs a comparison value.')
            normalized_rules.append(dict(question_id=parent['id'],operator=operator,value=value))
        item=dict(id=qid,label=label,help=text(q.get('help',''),'Help text',1000),type=kind,required=required,options=normalized,visible_to=visible,conditions=dict(mode=conditions['mode'],rules=normalized_rules))
        result['questions'].append(item);earlier[qid]=item
    return result


def evaluate(definition,regtypes,regtype_id,answers,check=False):
    page=validate(definition,regtypes)
    if not isinstance(regtype_id,str) or regtype_id not in {r['id'] for r in regtypes}:raise ValueError('Choose a current RegType.')
    if not isinstance(answers,dict) or len(answers)>50:raise ValueError('Preview answers must be an object with at most 50 entries.')
    effective={};visible=[];errors={};questions={q['id']:q for q in page['questions']}
    def matches(rule):
        key=rule['question_id']
        if key not in effective:return False
        actual=effective[key];operator=rule['operator'];expected=rule['value']
        if operator=='is_answered':return True
        if questions[key]['type']=='number':actual=decimal(actual);expected=decimal(expected)
        if operator=='equals':return actual==expected
        if operator=='not_equals':return actual!=expected
        if operator=='contains':return expected in actual
        if operator=='includes':return expected in actual
        if operator=='not_includes':return expected not in actual
        if operator=='gt':return actual>expected
        if operator=='gte':return actual>=expected
        if operator=='lt':return actual<expected
        if operator=='lte':return actual<=expected
        return False
    for q in page['questions']:
        rules=q['conditions']['rules']
        if q['visible_to'] is not None and regtype_id not in q['visible_to']:continue
        if rules and not (all(matches(r) for r in rules) if q['conditions']['mode']=='all' else any(matches(r) for r in rules)):continue
        visible.append(q['id'])
        try:
            value=answer(q,answers.get(q['id']))
            if value is not None:effective[q['id']]=value
            elif check and q['required']:errors[q['id']]='This question is required.'
        except ValueError as exc:
            if check:errors[q['id']]=str(exc)
    return dict(visible_ids=visible,effective_answers=effective,errors=errors)
