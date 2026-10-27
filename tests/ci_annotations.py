"""Expose failed unittest diagnostics through the normal GitHub Checks API.
The runner's result and exit code stay authoritative; reporting cannot mask them.
"""
import os
import unittest


def install():
    result=unittest.TextTestResult
    if os.environ.get('GITHUB_ACTIONS')!='true' or getattr(result,'_pushpull_annotations',False):
        return
    result._pushpull_annotations=True
    for name in ('addFailure','addError'):
        original=getattr(result,name)
        def report(self,test,error,_original=original):
            _original(self,test,error)
            try:
                message=test.id()+'\n'+self._exc_info_to_string(error,test)[-12000:]
                message=message.encode('utf-8','backslashreplace').decode('utf-8')
                message=message.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
                print('::error title=Unittest failure::'+message,flush=True)
            except Exception:
                pass  # The original failure was already recorded by unittest.
        setattr(result,name,report)
