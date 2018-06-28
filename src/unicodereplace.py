#-*- coding: UTF-8 -*-

def _unknown(unicodestring):
    """ don't change anything lol """
    return unicodestring

_fixings_ger = [
    (u'Ä', 'Ae'),
    (u'Ü', 'Ue'),
    (u'Ö', 'Oe'),
    (u'ä', 'ae'),
    (u'ü', 'ue'),
    (u'ö', 'oe'),
    (u'ß', 'ss')
]

def _fixgermanascii(unicodestring):
    for a, b in _fixings_ger:
        unicodestring = unicodestring.replace(a, b)
    return unicodestring

def asciiFixerFactory(languagecode):
    if languagecode == 'de-DE':
        return _fixgermanascii
    return _unknown
