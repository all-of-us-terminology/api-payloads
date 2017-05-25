import requests
import glob
import json
import sys
from copy import copy

CODEBOOK = 'http://terminology.pmi-ops.org/CodeSystem/ppi.json'
EXTRAS = 'http://terminology.pmi-ops.org/CodeSystem/ppi.json'
QUESTIONNAIRE_GLOB = '../questionnaire_payloads/*.json'

CONCEPTS_THAT_REPEAT = [
    'SecondaryContactInfo_PersonOneName',
    'SecondaryContactInfo_SecondContactsName',
    'PIIAddress_StreetAddress',
    'SecondaryContactInfo_SecondContactsAddress',
    'SecondaryContactInfo_PersonOneAddress']

def get_property(prop, c):
    matches = [p.get('valueCode') for p in c.get('property', []) if p.get('code') == prop]
    if matches: return matches[0]
    return None

def read_codebook(codebook=None, url=None, found=None, path_to_here=None):
    if codebook == None:
        codebook = requests.get(CODEBOOK).json()
        print "Evaluating Questionnaire against current codebook version: %s\n"%codebook['version']
        found = {}
        path_to_here = []
        url = codebook['url']
    for c in codebook.get('concept', []):
        found[(url, c['code'])] = {
            'code': c['code'],
            'system': url,
            'display': c['display'],
            'type': get_property('concept-type', c),
            'topic': get_property('concept-topic', c),
            'parents': path_to_here
        }
        read_codebook(c, url, found, path_to_here + [(url, c['code'])])
    return found

def read_questionnaire(questionnaire_label, q, found=None, level=0, path_to_here=None):
    question = q.get('question', [])
    group = q.get('group', [])

    if type(group) == dict:
        group = [group]

    if found == None:
        found = {}

    if path_to_here == None:
        path_to_here = []

    concept = q.get('concept', [])
    if concept:
        codes=[(c['system'], c.get('code', None)) for c in concept]
    else:
        codes = []

    for c in concept:
        c = copy(c)
        concept = (c.get('system'), c.get('code'))
        c['type'] = 'Module Name' if level == 1 else 'Question'
        c['source'] = questionnaire_label
        c['parents'] = path_to_here
        c['questionText'] = q.get('text', None)
        c['redefined'] = bool(found.get(concept))
        found[concept] = c
    for c in q.get('option', []):
        c = copy(c)
        concept = (c.get('system'), c.get('code'))
        c['type'] = 'Answer'
        c['source'] = questionnaire_label
        c['parents'] = path_to_here + codes
        c['redefined'] = bool(found.get(concept))
        found[concept] = c
    for part in group + question:
        read_questionnaire(questionnaire_label, part, found, level+1, path_to_here + codes)

    return found

def read_questionnaires():
    question_codes = {}
    files = glob.glob(QUESTIONNAIRE_GLOB)
    for fname in files:
        with open(fname) as f:
            read_questionnaire(fname.split("/")[-1], json.load(f), question_codes)
    return question_codes

codebook_codes = read_codebook()
questionnaire_codes = read_questionnaires()

errors = []
warnings = []

for q in questionnaire_codes:
    if q[0] == EXTRAS:
        continue
    if q not in codebook_codes:
        level = 'ERROR'
        if q[1] == None:
            level = 'WARNING'
        errors.append({
          'level': level,
          'questionnaire': questionnaire_codes[q]['source'],
          'code': str(q),
          'detail': 'Code not found in codebook'
        })
        continue
    qc = questionnaire_codes[q]
    cc = codebook_codes[q]
    qtype = questionnaire_codes[q]['type']
    cbtype = codebook_codes[q]['type']

    if qtype == 'Question' and qc.get('redefined'):
        if q[1] in CONCEPTS_THAT_REPEAT:
            continue
        errors.append({
          'level': 'ERROR',
          'questionnaire': questionnaire_codes[q]['source'],
          'code': str(q),
          'detail': 'Code assigned to multiple questions'
        })


    if qtype != cbtype:
        errors.append({
          'level': 'ERROR',
          'questionnaire': questionnaire_codes[q]['source'],
          'code': str(q),
          'detail': 'Questionnaire calls it a %s but codebook calls it a %s'%(qtype, cbtype)
        })

    if qtype == 'Answer':
        question = questionnaire_codes[q]['parents'][-1]
        codebook_answer = codebook_codes[q]
        try:
            parent_code_from_codebook = codebook_answer['parents'][-1]
            # Allow any question to have an answer that has 'PMI' as its parent code; these are the
            # base values found here:
            # https://docs.google.com/spreadsheets/d/1TNqJ1ekLFHF4vYA2SNCb-4NL8QgoJrfuJsxnUuXd-is/edit#gid=1791570240
            if parent_code_from_codebook[1] != 'PMI' and not set([question]) & set(codebook_answer['parents']):
                errors.append({
                'level': 'ERROR',
                'questionnaire': questionnaire_codes[q]['source'],
                'code': str(q),
                'detail': 'Questionnaire says this is an answer to %s but codebook says this is only valid in response to %s (or its parents)'%(question, parent_code_from_codebook)
                })

        except:
            errors.append({
            'level': 'ERROR',
            'questionnaire': questionnaire_codes[q]['source'],
            'code': str(q),
            'detail': 'Codebook version of this answer code appears not to have a parent question'
            })


for q in codebook_codes:
    if q not in questionnaire_codes:
        errors.append({
        'level': 'WARNING',
        'questionnaire': 'N/A',
        'code': str(q),
        'detail': 'Present in codebook but nt in any questionnaire'
        })

import pprint

errors = sorted(errors, key=lambda e: e['level'])
for e in errors:
    print "%s on %s from questionnaire %s"%(e['level'], e['code'], e['questionnaire'])
    print e['detail']
    print

if [e for e in errors if e['level'] == 'ERROR']:
    sys.exit(1)
