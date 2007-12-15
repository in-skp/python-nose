"""Utility functions and classes used by nose internally.
"""
import inspect
import logging
import os
import re
import sys
import types
import unittest
from compiler.consts import CO_GENERATOR
from types import ClassType, TypeType

log = logging.getLogger('nose')

ident_re = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')
class_types = (ClassType, TypeType)


def absdir(path):
    """Return absolute, normalized path to directory, if it exists; None
    otherwise.
    """
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.abspath(os.path.join(os.getcwd(),
                                                             path)))
    if path is None or not os.path.isdir(path):
        return None
    return path


def absfile(path, where=None):
    """Return absolute, normalized path to file (optionally in directory
    where), or None if the file can't be found either in where or the current
    working directory.
    """
    orig = path
    if where is None:
        where = os.getcwd()
    if isinstance(where, list) or isinstance(where, tuple):
        for maybe_path in where:
            maybe_abs = absfile(path, maybe_path)
            if maybe_abs is not None:
                return maybe_abs
        return None
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.abspath(os.path.join(where, path)))
    if path is None or not os.path.exists(path):
        if where != os.getcwd():
            # try the cwd instead
            path = os.path.normpath(os.path.abspath(os.path.join(os.getcwd(),
                                                                 orig)))
    if path is None or not os.path.exists(path):
        return None
    if os.path.isdir(path):
        # might want an __init__.py from pacakge
        init = os.path.join(path,'__init__.py')
        if os.path.isfile(init):
            return init
    elif os.path.isfile(path):
        return path
    return None


def anyp(predicate, iterable):
    for item in iterable:
        if predicate(item):
            return True
    return False


def file_like(name):
    """A name is file-like if it is a path that exists, or it has a
    directory part, or it ends in .py, or it isn't a legal python
    identifier.
    """
    return (os.path.exists(name)
            or os.path.dirname(name)
            or name.endswith('.py')
            or not ident_re.match(os.path.splitext(name)[0]))


def cmp_lineno(a, b):
    """Compare functions by their line numbers.
    
    >>> cmp_lineno(isgenerator, ispackage)
    -1
    >>> cmp_lineno(ispackage, isgenerator)
    1
    >>> cmp_lineno(isgenerator, isgenerator)
    0
    """
    return cmp(func_lineno(a), func_lineno(b))


def func_lineno(func):
    """Get the line number of a function. First looks for
    compat_co_firstlineno, then func_code.co_first_lineno.
    """
    try:
        return func.compat_co_firstlineno
    except AttributeError:
        try:
            return func.func_code.co_firstlineno
        except AttributeError:
            return -1


def isclass(obj):
    """Is obj a class? inspect's isclass is too liberal and returns True
    for objects that can't be subclasses of anything.
    """
    return type(obj) in class_types


def isgenerator(func):
    try:
        return func.func_code.co_flags & CO_GENERATOR != 0
    except AttributeError:
        return False
# backwards compat (issue #64)
is_generator = isgenerator


def ispackage(path):
    """
    Is this path a package directory?

    >>> ispackage('nose')
    True
    >>> ispackage('unit_tests')
    False
    >>> ispackage('nose/plugins')
    True
    >>> ispackage('nose/loader.py')
    False
    """
    if os.path.isdir(path):        
        init = [e for e in os.listdir(path)
                if os.path.isfile(os.path.join(path, e))
                and src(e) == '__init__.py']
        if init:
            return True
    return False


def getfilename(package, relativeTo=None):
    """Find the python source file for a package, relative to a
    particular directory (defaults to current working directory if not
    given).
    """
    if relativeTo is None:
        relativeTo = os.getcwd()
    path = os.path.join(relativeTo, os.sep.join(package.split('.')))
    suffixes = ('/__init__.py', '.py')
    for suffix in suffixes:
        filename = path + suffix
        if os.path.exists(filename):
            return filename
    return None
    

def getpackage(filename):
    """
    Find the full dotted package name for a given python source file
    name. Returns None if the file is not a python source file.
    
    >>> getpackage('foo.py')
    'foo'
    >>> getpackage('biff/baf.py')
    'baf'
    >>> getpackage('nose/util.py')
    'nose.util'

    Works for directories too.

    >>> getpackage('nose')
    'nose'
    >>> getpackage('nose/plugins')
    'nose.plugins'

    And __init__ files stuck onto directories

    >>> getpackage('nose/plugins/__init__.py')
    'nose.plugins'

    Absolute paths also work.

    >>> path = os.path.abspath(os.path.join('nose', 'plugins'))
    >>> getpackage(path)
    'nose.plugins'
    """
    src_file = src(filename)
    if not src_file.endswith('.py') and not ispackage(src_file):
        return None
    base, ext = os.path.splitext(os.path.basename(src_file))
    if base == '__init__':
        mod_parts = []
    else:
        mod_parts = [base]
    path, part = os.path.split(os.path.split(src_file)[0])
    while part:
        if ispackage(os.path.join(path, part)):
            mod_parts.append(part)
        else:
            break
        path, part = os.path.split(path)
    mod_parts.reverse()
    return '.'.join(mod_parts)


def ln(label):
    """Draw a 70-char-wide divider, with label in the middle.

    >>> ln('hello there')
    '---------------------------- hello there -----------------------------'
    """
    label_len = len(label) + 2
    chunk = (70 - label_len) / 2
    out = '%s %s %s' % ('-' * chunk, label, '-' * chunk)
    pad = 70 - len(out)
    if pad > 0:
        out = out + ('-' * pad)
    return out


def resolve_name(name, module=None):
    """Resolve a dotted name to a module and its parts. This is stolen
    wholesale from unittest.TestLoader.loadTestByName.

    >>> resolve_name('nose.util') #doctest: +ELLIPSIS
    <module 'nose.util' from...>
    >>> resolve_name('nose.util.resolve_name') #doctest: +ELLIPSIS
    <function resolve_name at...>
    """
    parts = name.split('.')
    parts_copy = parts[:]
    if module is None:
        while parts_copy:
            try:
                log.debug("__import__ %s", name)
                module = __import__('.'.join(parts_copy))
                break
            except ImportError:
                del parts_copy[-1]
                if not parts_copy:
                    raise
        parts = parts[1:]
    obj = module
    log.debug("resolve: %s, %s, %s, %s", parts, name, obj, module)
    for part in parts:
        obj = getattr(obj, part)
    return obj


def split_test_name(test):
    """Split a test name into a 3-tuple containing file, module, and callable
    names, any of which (but not all) may be blank.

    Test names are in the form:

    file_or_module:callable

    Either side of the : may be dotted. To change the splitting behavior, you
    can alter nose.util.split_test_re.
    """
    norm = os.path.normpath
    file_or_mod = test
    fn = None
    if not ':' in test:
        # only a file or mod part
        if file_like(test):
            return (norm(test), None, None)
        else:
            return (None, test, None)

    # could be path|mod:callable, or a : in the file path someplace
    head, tail = os.path.split(test)
    if not head:
        # this is a case like 'foo:bar' -- generally a module
        # name followed by a callable, but also may be a windows
        # drive letter followed by a path
        try:
            file_or_mod, fn = test.split(':')
            if file_like(fn):
                # must be a funny path
                file_or_mod, fn = test, None
        except ValueError:
            # more than one : in the test
            # this is a case like c:\some\path.py:a_test
            parts = test.split(':')
            if len(parts[0]) == 1:
                file_or_mod, fn = ':'.join(parts[:-1]), parts[-1]
            else:
                # nonsense like foo:bar:baz
                raise ValueError("Test name '%s' could not be parsed. Please "
                                 "format test names as path:callable or "
                                 "module:callable.")
    elif not tail:
        # this is a case like 'foo:bar/'
        # : must be part of the file path, so ignore it
        file_or_mod = test
    else:
        if ':' in tail:
            file_part, fn = tail.split(':')
        else:
            file_part = tail
        file_or_mod = os.sep.join([head, file_part])
    if file_or_mod:
        if file_like(file_or_mod):
            return (norm(file_or_mod), None, fn)
        else:
            return (None, file_or_mod, fn)
    else:
        return (None, None, fn)
split_test_name.__test__ = False # do not collect

    
def test_address(test):
    """Find the test address for a test, which may be a module, filename,
    class, method or function.
    """
    try:
        return test.address()
    except AttributeError:
        pass
    # type-based polymorphism sucks in general, but I believe is
    # appropriate here
    t = type(test)
    file = module = call = None
    if t == types.ModuleType:
        file = getattr(test, '__file__', None)
        module = getattr(test, '__name__', None)
        return (file, module, call)
    if t == types.FunctionType or t in (type, types.ClassType):
        module = getattr(test, '__module__', None)
        if module is not None:
            m = sys.modules[module]
            file = getattr(m, '__file__', None)
            if file is not None:
                file = os.path.abspath(file)
        call = getattr(test, '__name__', None)
        return (file, module, call)
    if t == types.InstanceType:
        return test_address(test.__class__)
    if t == types.MethodType:
        cls_adr = test_address(test.im_class)
        return (cls_adr[0], cls_adr[1],
                "%s.%s" % (cls_adr[2], test.__name__))
    # handle unittest.TestCase instances
    if isinstance(test, unittest.TestCase):
        if hasattr(test, '_FunctionTestCase__testFunc'):
            # unittest FunctionTestCase
            return test_address(test._FunctionTestCase__testFunc)
        # regular unittest.TestCase
        cls_adr = test_address(test.__class__)
        # 2.5 compat: __testMethodName changed to _testMethodName
        try:
            method_name = test._TestCase__testMethodName
        except AttributeError:
            method_name = test._testMethodName
        return (cls_adr[0], cls_adr[1],
                "%s.%s" % (cls_adr[2], method_name))
    raise TypeError("I don't know what %s is (%s)" % (test, t))
test_address.__test__ = False # do not collect


def try_run(obj, names):
    """Given a list of possible method names, try to run them with the
    provided object. Keep going until something works. Used to run
    setup/teardown methods for module, package, and function tests.
    """
    for name in names:
        func = getattr(obj, name, None)
        if func is not None:
            if type(obj) == types.ModuleType:
                # py.test compatibility
                try:
                    args, varargs, varkw, defaults = inspect.getargspec(func)
                except TypeError:
                    # Not a function. If it's callable, call it anyway
                    if hasattr(func, '__call__'):
                        func = func.__call__
                    try:
                        args, varargs, varkw, defaults = \
                            inspect.getargspec(func)
                        args.pop(0) # pop the self off
                    except TypeError:
                        raise TypeError("Attribute %s of %r is not a python "
                                        "function. Only functions or callables"
                                        " may be used as fixtures." %
                                        (name, obj))                    
                if len(args):
                    log.debug("call fixture %s.%s(%s)", obj, name, obj)    
                    return func(obj)
            log.debug("call fixture %s.%s", obj, name)
            return func()


def src(filename):
    """Find the python source file for a .pyc or .pyo file. Returns the 
    filename provided if it is not a python source file.
    """
    if filename is None:
        return filename
    base, ext = os.path.splitext(filename)
    if ext in ('.pyc', '.pyo', '.py'):
        return '.'.join((base, 'py'))
    return filename


def match_last(a, b, regex):
    """Sort compare function that puts items that match a
    regular expression last.

    >>> from nose.config import Config
    >>> c = Config()
    >>> regex = c.testMatch
    >>> entries = ['.', '..', 'a_test', 'src', 'lib', 'test', 'foo.py']
    >>> entries.sort(lambda a, b: match_last(a, b, regex))
    >>> entries
    ['.', '..', 'foo.py', 'lib', 'src', 'a_test', 'test']
    """
    if regex.search(a) and not regex.search(b):
        return 1
    elif regex.search(b) and not regex.search(a):
        return -1
    return cmp(a, b)

        
def tolist(val):
    """Convert a value that may be a list or a (possibly comma-separated)
    string into a list. The exception: None is returned as None, not [None].

    >>> tolist(["one", "two"])
    ['one', 'two']
    >>> tolist("hello")
    ['hello']
    >>> tolist("separate,values, with, commas,  spaces , are    ,ok")
    ['separate', 'values', 'with', 'commas', 'spaces', 'are', 'ok']
    """
    if val is None:
        return None
    try:
        # might already be a list
        val.extend([])
        return val
    except AttributeError:
        pass
    # might be a string
    try:
        return re.split(r'\s*,\s*', val)
    except TypeError:
        # who knows... 
        return list(val)


class odict(dict):
    """Simple ordered dict implementation, based on:

    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/107747
    """
    def __init__(self, *arg, **kw):
        self._keys = []
        super(odict, self).__init__(*arg, **kw)

    def __delitem__(self, key):
        super(odict, self).__delitem__(key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        super(odict, self).__setitem__(key, item)
        if key not in self._keys:
            self._keys.append(key)

    def __str__(self):
        return "{%s}" % ', '.join(["%r: %r" % (k, v) for k, v in self.items()])

    def clear(self):
        super(odict, self).clear()
        self._keys = []

    def copy(self):
        d = super(odict, self).copy()
        d._keys = self._keys[:]
        return d

    def items(self):
        return zip(self._keys, self.values())

    def keys(self):
        return self._keys[:]

    def setdefault(self, key, failobj=None):
        item = super(odict, self).setdefault(key, failobj)
        if key not in self._keys:
            self._keys.append(key)
        return item

    def update(self, dict):
        super(odict, self).update(dict)
        for key in dict.keys():
            if key not in self._keys:
                self._keys.append(key)

    def values(self):
        return map(self.get, self._keys)



if __name__ == '__main__':
    import doctest
    doctest.testmod()
