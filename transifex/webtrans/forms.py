import re
import polib
from django import forms
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string


def calculate_rows(entry):
    text = getattr(entry, 'msgid', entry)
    if isinstance(text, str):
        text = text.decode(getattr(entry, 'encoding', 'UTF-8'))
    replacement = polib.escape(text).replace(r'\n','<br />\n')
    lines = mark_safe(replacement).split(u'\n')
    return sum(len(line)/40 for k, line in enumerate(lines)) + 1


def guess_entry_status(entry):
    if entry.translated() and not entry.obsolete:
        return 'translated'
    elif 'fuzzy' in entry.flags:
        return 'fuzzy'
    elif not entry.translated() and not entry.obsolete:
        return 'untranslated'


def _get_label(msgid_list):
    """Return the label for a plural field."""
    return render_to_string('webtrans/msgid_label.html',
                            { 'msgid_list': msgid_list})


class PluralMessageWidget(forms.MultiWidget):
    """A widget to render plural translatable strings."""
    def __init__(self, messages, attrs=None):
        widgets=[]
        for i, entry in enumerate(messages):
            widgets.append(forms.Textarea(attrs=attrs))
        super(PluralMessageWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value.split('#|#')
        return ['']


class PluralMessageField(forms.MultiValueField):
    """A field for plural translatable strings."""
    def __init__(self, entry, initial, attrs={}, widget=None, *args, **kwargs):
        attrs.update({'rows': calculate_rows(entry)})
        fields = []
        for i in initial:
            fields.append(forms.CharField(label=entry.msgid_plural))

        if not widget:
            widget=PluralMessageWidget(initial, attrs=attrs)
        super(PluralMessageField, self).__init__(fields, initial=initial, 
            widget=widget, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return "#|#".join(unicode(data) for data in data_list)
        return None


class MessageField(forms.CharField):
    """A field for translatable strings."""
    def __init__(self, entry, attrs={}, widget=None, *args, **kwargs):
        attrs.update({'rows': calculate_rows(entry)})
        if not widget:
            widget=MessageWidget(attrs=attrs)
        super(MessageField, self).__init__(attrs, widget=widget, *args, **kwargs)


class MessageWidget(forms.Textarea):
    """A widget to render translatable strings."""
    def __init__(self, attrs=None, *args, **kwargs):
        super(MessageWidget, self).__init__(attrs, *args, **kwargs)


class TranslationForm(forms.Form):

    def __init__(self, po_entries, *args, **kwargs):
        super(TranslationForm, self).__init__(*args, **kwargs)
        k=1;
        for entry in po_entries:
            if entry.obsolete == 0:
                entry_status = guess_entry_status(entry)
                fuzzy = False
                if entry_status == 'fuzzy':
                    fuzzy = True

                attrs = {'class':'%s msgstr_field_%s' % (entry_status, k),
                         'title':'%s' % polib.escape(entry.comment)}

                if entry.msgid_plural:
                    message_keys = entry.msgstr_plural.keys()
                    message_keys.sort()
                    messages = [entry.msgstr_plural[key] for key in message_keys]
                    msgstr_field = PluralMessageField(
                        entry=entry,
                        initial=messages,
                        help_text=self.help_text(entry),
                        label=_get_label([polib.escape(entry.msgid),
                            polib.escape(entry.msgid_plural)]),
                        attrs=attrs
                    )
                else:
                    msgstr_field = MessageField(
                        entry=entry,
                        initial=polib.escape(entry.msgstr),
                        help_text=self.help_text(entry),
                        attrs=attrs,
                        label=_get_label([polib.escape(entry.msgid)])
                        )

                msgid_field = MessageField(entry=entry, widget=forms.HiddenInput,
                    initial=polib.escape(entry.msgid))

                fuzzy_field = forms.BooleanField(required=False, initial=fuzzy)

                changed_field = forms.BooleanField(required=False, initial=False,
                    widget=forms.HiddenInput)

                self.fields['msgid_field_%s' % k] = msgid_field
                self.fields['fuzzy_field_%s' % k] = fuzzy_field
                self.fields['msgstr_field_%s' % k] = msgstr_field
                self.fields['changed_field_%s' % k] = changed_field

                k += 1;

    def help_text(self, entry):
        occurrences = ["%s (line %s)" % (file, line) for (file, line) in entry.occurrences]
        return '<small>%s</small>'% (', '.join(occurrences))
