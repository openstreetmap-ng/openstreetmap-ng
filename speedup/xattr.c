#include <Python.h>
#include <tupleobject.h>

#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)

typedef struct {
  const char *key;
  PyObject *value;
} StringCacheEntry;

static StringCacheEntry *xattr_cache = nullptr;

static PyObject *
xattr_json(PyObject *, PyObject *const *args, Py_ssize_t nargs, PyObject *) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) < 1 || !PyUnicode_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }
  Py_INCREF(args[0]);
  return args[0];
}

static PyObject *
xattr_xml(PyObject *, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) < 1 || !PyUnicode_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  // Use `xml` parameter if provided, otherwise use `name`.
  PyObject *source = args[0];
  if ((PyVectorcall_NARGS(nargs) > 1 || (kwnames && PyTuple_GET_SIZE(kwnames))) &&
      args[1] != Py_None) {
    if (UNLIKELY(!PyUnicode_CheckExact(args[1]))) {
      PyErr_BadArgument();
      return nullptr;
    }
    source = args[1];
  }

  const char *source_c = PyUnicode_AsUTF8(source);
  if (UNLIKELY(!source_c))
    return nullptr;

  PyObject *cached = shget(xattr_cache, source_c);

  // Cache hit
  if (LIKELY(cached != nullptr)) {
    Py_INCREF(cached);
    return cached;
  }

  // Cache miss
  PyObject *result = PyUnicode_FromFormat("@%s", source_c);
  if (UNLIKELY(!result))
    return nullptr;

  shput(xattr_cache, source_c, result);
  Py_INCREF(result);
  return result;
}

static PyMethodDef methods[] = {
  {"xattr_json", _PyCFunction_CAST(xattr_json), METH_FASTCALL | METH_KEYWORDS, nullptr},
  {"xattr_xml", _PyCFunction_CAST(xattr_xml), METH_FASTCALL | METH_KEYWORDS, nullptr},
  {nullptr, nullptr, 0, nullptr},
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "speedup.xattr",
  nullptr,
  -1,
  methods,
  nullptr,
  nullptr,
  nullptr,
  nullptr
};

PyMODINIT_FUNC
PyInit_xattr(void) {
  sh_new_arena(xattr_cache);
  return PyModule_Create(&module);
}
