#include "libxml/tree.h"
#include "libxml/xmlstring.h"
#include <Python.h>
#include <datetime.h>

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)

#pragma region CDATA

typedef struct {
  PyObject_HEAD PyObject *text;
} CDATAObject;

static PyObject *
CDATA_new(PyTypeObject *type, PyObject *args, PyObject *) {
  PyObject *text;
  if (UNLIKELY(!PyArg_ParseTuple(args, "U:CDATA", &text)))
    return nullptr;

  CDATAObject *self = (CDATAObject *)type->tp_alloc(type, 0);
  if (UNLIKELY(!self))
    return nullptr;

  Py_INCREF(text);
  self->text = text;
  return (PyObject *)self;
}

static PyObject *
CDATA_str(CDATAObject *self) {
  Py_INCREF(self->text);
  return self->text;
}

static PyObject *
CDATA_repr(CDATAObject *self) {
  return PyUnicode_FromFormat("CDATA(%R)", self->text);
}

static void
CDATA_dealloc(CDATAObject *self) {
  Py_DECREF(self->text);
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyTypeObject CDATAType = {
  PyVarObject_HEAD_INIT(nullptr, 0).tp_name = "speedup.xml_unparse.CDATA",
  .tp_basicsize = sizeof(CDATAObject),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_IMMUTABLETYPE,
  .tp_new = CDATA_new,
  .tp_dealloc = (destructor)CDATA_dealloc,
  .tp_str = (reprfunc)CDATA_str,
  .tp_repr = (reprfunc)CDATA_repr,
};

#pragma endregion
#pragma region Stringify

// If obj is set, it must be freed by the caller.
// If both fields are nullptr, an error has occurred.
typedef struct {
  const char *str;
  PyObject *obj;
} toStringResult;

static toStringResult
to_string(PyObject *value) {
  if (value == Py_True)
    return (toStringResult){.str = "true"};
  if (value == Py_False)
    return (toStringResult){.str = "false"};
  if (value == Py_None)
    return (toStringResult){.str = ""};
  if (PyUnicode_CheckExact(value)) {
    Py_INCREF(value);
    return (toStringResult){.obj = value};
  }

  if (PyDateTime_CheckExact(value)) {
    PyObject *tzinfo = PyDateTime_DATE_GET_TZINFO(value);
    if (UNLIKELY(tzinfo != Py_None && tzinfo != PyDateTime_TimeZone_UTC)) {
      PyErr_Format(PyExc_ValueError, "Timezone must be UTC, got %R", tzinfo);
      return (toStringResult){};
    }

    auto us = PyDateTime_DATE_GET_MICROSECOND(value);
    const char *format =
      us ? "%04d-%02d-%02dT%02d:%02d:%02d.%06dZ" : "%04d-%02d-%02dT%02d:%02d:%02dZ";
    PyObject *result = PyUnicode_FromFormat(
      format, PyDateTime_GET_YEAR(value), PyDateTime_GET_MONTH(value),
      PyDateTime_GET_DAY(value), PyDateTime_DATE_GET_HOUR(value),
      PyDateTime_DATE_GET_MINUTE(value), PyDateTime_DATE_GET_SECOND(value), us
    );

    return (toStringResult){.obj = result};
  }

  // For all other types, convert to string
  return (toStringResult){.obj = PyObject_Str(value)};
}

#pragma endregion
#pragma region Unparse Helpers

static bool
unparse_element(
  xmlDocPtr doc, xmlNodePtr parent, const char *key, PyObject *value, bool is_root
);

static bool
unparse_scalar(xmlDocPtr doc, xmlNodePtr parent, const char *key, PyObject *value) {
  xmlNodePtr element = xmlNewChild(parent, nullptr, BAD_CAST key, nullptr);
  if (UNLIKELY(!element)) {
    PyErr_NoMemory();
    return false;
  }

  // Special handling for CDATA
  if (Py_TYPE(value) == &CDATAType) {
    Py_ssize_t size;
    const char *str = PyUnicode_AsUTF8AndSize(((CDATAObject *)value)->text, &size);
    assert(0 <= size && size <= INT_MAX);

    xmlNodePtr cdata = xmlNewCDataBlock(doc, BAD_CAST str, size);
    if (UNLIKELY(!cdata)) {
      PyErr_NoMemory();
      return false;
    }

    xmlAddChild(element, cdata);
    return true;
  }

  auto result = to_string(value);
  int add_result;

  if (result.str)
    add_result = xmlNodeAddContent(element, BAD_CAST result.str);
  else if (result.obj) {
    Py_ssize_t size;
    const char *str = PyUnicode_AsUTF8AndSize(result.obj, &size);
    assert(0 <= size && size <= INT_MAX);
    add_result = xmlNodeAddContentLen(element, BAD_CAST str, size);
    Py_DECREF(result.obj);
  } else
    return false;

  if (UNLIKELY(add_result < 0)) {
    PyErr_NoMemory();
    return false;
  }
  return !add_result;
}

static bool
unparse_item(xmlDocPtr doc, xmlNodePtr element, const char *key, PyObject *value) {
  if (key[0] == '@') { // Is attribute
    auto result = to_string(value);
    xmlAttrPtr attr;

    if (result.str)
      attr = xmlNewProp(element, BAD_CAST key + 1, BAD_CAST result.str);
    else if (result.obj) {
      attr =
        xmlNewProp(element, BAD_CAST key + 1, BAD_CAST PyUnicode_AsUTF8(result.obj));
      Py_DECREF(result.obj);
    } else
      return false;

    if (UNLIKELY(!attr)) {
      PyErr_NoMemory();
      return false;
    }
    return true;
  } else if (key[0] == '#' && LIKELY(!strcmp(key, "#text"))) { // Is text

    // Special handling for CDATA
    if (Py_TYPE(value) == &CDATAType) {
      Py_ssize_t size;
      const char *str = PyUnicode_AsUTF8AndSize(((CDATAObject *)value)->text, &size);
      assert(0 <= size && size <= INT_MAX);

      xmlNodePtr cdata = xmlNewCDataBlock(doc, BAD_CAST str, size);
      if (UNLIKELY(!cdata)) {
        PyErr_NoMemory();
        return false;
      }

      xmlAddChild(element, cdata);
      return true;
    }

    auto result = to_string(value);
    int add_result;

    if (result.str)
      add_result = xmlNodeAddContent(element, BAD_CAST result.str);
    else if (result.obj) {
      Py_ssize_t size;
      const char *str = PyUnicode_AsUTF8AndSize(result.obj, &size);
      assert(0 <= size && size <= INT_MAX);
      add_result = xmlNodeAddContentLen(element, BAD_CAST str, size);
      Py_DECREF(result.obj);
    } else
      return false;

    if (UNLIKELY(add_result < 0)) {
      PyErr_NoMemory();
      return false;
    }
    return !add_result;
  } else
    return unparse_element(doc, element, key, value, false);
}

static bool
unparse_dict(xmlDocPtr doc, xmlNodePtr parent, const char *key, PyObject *value) {
  xmlNodePtr element = xmlNewChild(parent, nullptr, BAD_CAST key, nullptr);
  if (UNLIKELY(!element)) {
    PyErr_NoMemory();
    return false;
  }

  PyObject *dict_key, *dict_value;
  Py_ssize_t pos = 0;

  while (PyDict_Next(value, &pos, &dict_key, &dict_value)) {
    if (UNLIKELY(!PyUnicode_CheckExact(dict_key))) {
      PyErr_SetString(PyExc_TypeError, "Dictionary keys must be strings");
      return false;
    }

    if (UNLIKELY(!unparse_item(doc, element, PyUnicode_AsUTF8(dict_key), dict_value)))
      return false;
  }

  return true;
}

static bool
unparse_element(
  xmlDocPtr doc, xmlNodePtr parent, const char *key, PyObject *value, bool is_root
) {

  if (PyDict_CheckExact(value)) {
    // Encode dict
    return unparse_dict(doc, parent, key, value);
  } else if (PyList_CheckExact(value) || PyTuple_CheckExact(value)) {
    // Encode sequence of ...
    auto is_list = PyList_CheckExact(value);
    auto size = is_list ? PyList_GET_SIZE(value) : PyTuple_GET_SIZE(value);
    xmlNodePtr tuples_element = nullptr;

    for (typeof(size) i = 0; i < size; i++) {
      PyObject *item = is_list ? PyList_GET_ITEM(value, i) : PyTuple_GET_ITEM(value, i);

      if (PyDict_CheckExact(item)) {
        // ... dicts
        if (UNLIKELY(is_root && size > 1)) {
          PyErr_SetString(
            PyExc_ValueError, "Root element cannot contain multiple dicts"
          );
          return false;
        }

        if (UNLIKELY(!unparse_dict(doc, parent, key, item)))
          return false;

      } else if (PyList_CheckExact(item) || PyTuple_CheckExact(item)) {
        // ... (key, value) tuples
        if (!tuples_element) {
          tuples_element = xmlNewChild(parent, nullptr, BAD_CAST key, nullptr);
          if (UNLIKELY(!tuples_element)) {
            PyErr_NoMemory();
            return false;
          }
        }

        auto item_is_list = UNLIKELY(PyList_CheckExact(item));
        auto item_size = item_is_list ? PyList_GET_SIZE(item) : PyTuple_GET_SIZE(item);
        if (UNLIKELY(item_size != 2)) {
          PyErr_SetString(
            PyExc_ValueError, "Sequence tuples must be (key, value) pairs"
          );
          return false;
        }

        PyObject *tuple_key =
          item_is_list ? PyList_GET_ITEM(item, 0) : PyTuple_GET_ITEM(item, 0);
        PyObject *tuple_value =
          item_is_list ? PyList_GET_ITEM(item, 1) : PyTuple_GET_ITEM(item, 1);
        if (UNLIKELY(!PyUnicode_CheckExact(tuple_key))) {
          PyErr_SetString(PyExc_TypeError, "Sequence tuples keys must be strings");
          return false;
        }

        if (UNLIKELY(!unparse_item(
              doc, tuples_element, PyUnicode_AsUTF8(tuple_key), tuple_value
            )))
          return false;

      } else { // ... scalars
        if (UNLIKELY(is_root && size > 1)) {
          PyErr_SetString(
            PyExc_ValueError, "Root element cannot contain multiple scalars"
          );
          return false;
        }

        if (UNLIKELY(!unparse_scalar(doc, parent, key, item)))
          return false;
      }
    }

    return true;
  } else {
    // Encode scalar
    return unparse_scalar(doc, parent, key, value);
  }
}

#pragma endregion

static PyObject *
xml_unparse(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(
        PyVectorcall_NARGS(nargs) != 2 || !PyDict_CheckExact(args[0]) ||
        !PyBool_Check(args[1])
      )) {
    PyErr_BadArgument();
    return nullptr;
  }
  if (UNLIKELY(PyDict_GET_SIZE(args[0]) != 1)) {
    PyErr_SetString(PyExc_ValueError, "Invalid root element count");
    return nullptr;
  }

  PyObject *key, *value;
  Py_ssize_t pos = 0;
  PyDict_Next(args[0], &pos, &key, &value);
  if (UNLIKELY(!PyUnicode_CheckExact(key))) {
    PyErr_SetString(PyExc_TypeError, "Root key must be a string");
    return nullptr;
  }

  xmlDocPtr doc = xmlNewDoc(nullptr);
  if (UNLIKELY(!doc)) {
    PyErr_NoMemory();
    return nullptr;
  }

  xmlNodePtr dummy = xmlNewNode(nullptr, BAD_CAST "X");
  if (UNLIKELY(!dummy)) {
    PyErr_NoMemory();
    xmlFreeDoc(doc);
    return nullptr;
  }

  if (UNLIKELY(!unparse_element(doc, dummy, PyUnicode_AsUTF8(key), value, true))) {
    const xmlError *error = xmlGetLastError();
    if (error)
      PyErr_Format(
        PyExc_ValueError, "Error unparsing XML: %s",
        error->message ? error->message : "Unknown error"
      );
    xmlResetLastError();
    xmlFreeDoc(doc);
    xmlFreeNode(dummy);
    return nullptr;
  }

  xmlDocSetRootElement(doc, xmlGetLastChild(dummy));

  xmlChar *doc_str;
  int doc_size = 0;
  xmlDocDumpFormatMemoryEnc(doc, &doc_str, &doc_size, "UTF-8", 0);

  PyObject *result = Py_IsTrue(args[1])
                       ? PyBytes_FromStringAndSize((char *)doc_str, doc_size)
                       : PyUnicode_FromStringAndSize((char *)doc_str, doc_size);
  xmlFree(doc_str);
  xmlFreeDoc(doc);
  dummy->children = nullptr;
  xmlFreeNode(dummy);
  return result;
}

static PyMethodDef methods[] = {
  {"xml_unparse", _PyCFunction_CAST(xml_unparse), METH_FASTCALL, nullptr},
  {nullptr, nullptr, 0, nullptr},
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "speedup.xml_unparse",
  nullptr,
  -1,
  methods,
  nullptr,
  nullptr,
  nullptr,
  nullptr
};

PyMODINIT_FUNC
PyInit_xml_unparse(void) {
  PyDateTime_IMPORT;

  PyObject *m = PyModule_Create(&module);

  PyType_Ready(&CDATAType);
  PyModule_Add(m, "CDATA", (PyObject *)&CDATAType);

  return m;
}
