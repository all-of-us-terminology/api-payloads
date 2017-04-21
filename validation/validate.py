import requests
import glob
import json
import sys
from copy import copy

CODEBOOK = 'http://terminology.pmi-ops.org/CodeSystem/ppi.json'
QUESTIONNAIRE_GLOB = '../questionnaire_payloads/*.json'

def get_property(prop, c):
    matches = [p.get('valueCode') for p in c.get('property', []) if p.get('code') == prop]
    if matches: return matches[0]
    return None

def read_codebook(codebook=None, url=None, found=None):
    if codebook == None:
        codebook = requests.get(CODEBOOK).json()
        found = {}
        url = codebook['url']
    for c in codebook.get('concept', []):
        found[(url, c['code'])] = {
            'code': c['code'],
            'system': url,
            'type': get_property('concept-type', c),
            'topic': get_property('concept-topic', c),
        }
        read_codebook(c, url, found)
    return found

def read_questionnaire(q, found=None, level=0):
    qtype = 'Question'
    question = q.get('question', [])
    group = q.get('group', [])

    if type(group) == dict:
        group = [group]

    if found == None:
        found = {}

    concept = q.get('concept', [])
    for c in concept:
        c = copy(c)
        c['type'] = 'Module Name' if level == 1 else 'Question'
        found[(c.get('system'), c.get('code'))] = c
    for c in q.get('option', []):
        c = copy(c)
        c['type'] = 'Answer'
        found[(c.get('system'), c.get('code'))] = c
    for part in group + question:
        read_questionnaire(part, found, level+1)

    return found

def read_questionnaires():
    question_codes = {}
    files = glob.glob(QUESTIONNAIRE_GLOB)
    for fname in files:
        with open(fname) as f:
            read_questionnaire(json.load(f), question_codes)
    return question_codes

codebook_codes = read_codebook()
questionnaire_codes = read_questionnaires()

errors = []
warnings = []

for q in questionnaire_codes:
    if q not in codebook_codes:
        errors.append("ERROR: %s in questionnaire but not in codebook"%str(q))
        continue
    qtype = questionnaire_codes[q]['type']
    cbtype = codebook_codes[q]['type']
    if qtype != cbtype:
        errors.append("ERROR: %s in questionnaire is a %s, but codebook says it's a %s"%(q[1], qtype, cbtype))

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

if errors:
    sys.exit(1)
