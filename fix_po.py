import re

def get_existing_msgids(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    return set(re.findall(r'^msgid "(.+?)"', content, re.MULTILINE))

en_existing = get_existing_msgids('locale/en/LC_MESSAGES/django.po')
ru_existing = get_existing_msgids('locale/ru/LC_MESSAGES/django.po')
hy_existing = get_existing_msgids('locale/hy/LC_MESSAGES/django.po')

dupes = ['Full name', 'Confirm password', 'Login', 'Email', 'Subject', 'Message',
         'Register', 'Delete', 'Status', 'Support', 'Cancel', 'Remove', 'Yes', 'No',
         'Success', 'Balance', 'Date', 'Amount', 'Reason', 'New password',
         'Update password', 'Current password', 'Log out']
print("Duplicates in en:", [d for d in dupes if d in en_existing])
print("Duplicates in ru:", [d for d in dupes if d in ru_existing])
