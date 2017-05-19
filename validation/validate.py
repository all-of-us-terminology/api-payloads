import requests
import glob
import json
import sys
from copy import copy

CODEBOOK = 'http://terminology.pmi-ops.org/CodeSystem/ppi.json'
EXTRAS = 'http://terminology.pmi-ops.org/CodeSystem/ppi.json'
QUESTIONNAIRE_GLOB = '../questionnaire_payloads/*.json'

def get_property(prop, c):
    matches = [p.get('valueCode') for p in c.get('property', []) if p.get('code') == prop]
    if matches: return matches[0]
    return None

def read_codebook(codebook=None, url=None, found=None, path_to_here=None):
    if codebook == None:
        codebook = requests.get(CODEBOOK).json()
        found = {}
        path_to_here = []
        url = codebook['url']
    for c in codebook.get('concept', []):
        found[(url, c['code'])] = {
            'code': c['code'],
            'system': url,
            'type': get_property('concept-type', c),
            'topic': get_property('concept-topic', c),
            'parents': path_to_here
        }
        read_codebook(c, url, found, path_to_here + [(url, c['code'])])
    return found

def read_questionnaire(questionnaire_label, q, found=None, path_to_here=None):
    question = q.get('question', [])
    group = q.get('group', [])

    if type(group) == dict:
        group = [group]

    if found == None:
        found = {}

    if path_to_here == None:
        path_to_here = []

    level = len(path_to_here)

    concept = q.get('concept', [])
    if concept:
        codes=[(c['system'], c.get('code', None)) for c in concept]
    else:
        codes = []

    for c in concept:
        c = copy(c)
        c['type'] = 'Module Name' if level == 1 else 'Question'
        c['source'] = questionnaire_label
        c['parents'] = path_to_here
        found[(c.get('system'), c.get('code'))] = c
    for c in q.get('option', []):
        c = copy(c)
        c['type'] = 'Answer'
        c['source'] = questionnaire_label
        c['parents'] = path_to_here + codes
        found[(c.get('system'), c.get('code'))] = c
    for part in group + question:
        read_questionnaire(questionnaire_label, part, found, path_to_here + codes)

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
        errors.append("ERROR: %s in questionnaire '%s' but not in codebook"%(str(q), questionnaire_codes[q]['source']))
        continue
    qtype = questionnaire_codes[q]['type']
    cbtype = codebook_codes[q]['type']
    if qtype != cbtype:
        errors.append("ERROR: %s in questionnaire '%s' is a %s, but codebook says it's a %s"%(questionnaire_codes[q]['source'], q[1], qtype, cbtype))
    if qtype == 'Answer':
        question = questionnaire_codes[q]['parents'][-1]
        codebook_answer = codebook_codes[q]
        if not set([question]) & set(codebook_answer['parents']):
            errors.append("ERROR: Answer %s in questionnaire '%s' is listed as a response to question %s, but codebook says it's only valid as an answer to %s (or its parents)"%(q, questionnaire_codes[q]['source'], question, codebook_answer['parents'][-1]))


for q in codebook_codes:
    if q not in questionnaire_codes:
        warnings.append("WARNING: %s in codebook but not in questionnaire"%str(q))

print len(errors), "errors"
print len(warnings), "warnings"
print
print "errors"
print "\n".join(errors)
print
print "warnings"
print "\n".join(warnings)

#for k, v in questionnaire_codes.iteritems():
#    print v

if errors:
    sys.exit(1)
