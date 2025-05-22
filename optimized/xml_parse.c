#include <Python.h>
#include <stdlib.h>

#include "libxml/xmlreader.h"
#include "libxml/xmlstring.h"

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)

#define LIST_PREALLOC_SIZE 8

#pragma region Globals

static PyObject *fromisoformat_func = nullptr;
static PyObject *parse_date_func = nullptr;

#pragma endregion
#pragma region Sets

// These arrays MUST be sorted alphabetically for bsearch to work
static const char *force_items_set[] = {"bounds", "create",   "delete", "modify",
                                        "node",   "relation", "way"};
static const char *force_list_set[] = {"comment", "gpx_file",   "member", "nd",
                                       "note",    "preference", "tag",    "trk",
                                       "trkpt",   "trkseg"};

static int
in_set_cmp(const void *key, const void *element) {
  return strcmp((const char *)key, *(const char **)element);
}

static bool
in_set(const char *str, size_t set_size, const char *set[static set_size]) {
  return bsearch(str, set, set_size, sizeof(char *), in_set_cmp) != nullptr;
}

#pragma endregion
#pragma region Postprocessors

static PyObject *
postprocess_xml_str(const xmlChar *value_xml) {
  return PyUnicode_FromString((const char *)value_xml);
}

static PyObject *
postprocess_xml_int(const xmlChar *value_xml) {
  errno = 0;
  auto value = strtoll((const char *)value_xml, nullptr, 10);
  return LIKELY(!errno) ? PyLong_FromLongLong(value) : nullptr;
}

static PyObject *
postprocess_xml_float(const xmlChar *value_xml) {
  errno = 0;
  auto value = strtod((const char *)value_xml, nullptr);
  return LIKELY(!errno) ? PyFloat_FromDouble(value) : nullptr;
}

static PyObject *
postprocess_xml_bool(const xmlChar *value_xml) {
  if (!strcmp((const char *)value_xml, "true"))
    Py_RETURN_TRUE;
  else if (!strcmp((const char *)value_xml, "false"))
    Py_RETURN_FALSE;
  else
    return nullptr;
}

static PyObject *
postprocess_xml_version(const xmlChar *value_xml) {
  return xmlStrchr(value_xml, (xmlChar)'.') ? postprocess_xml_float(value_xml)
                                            : postprocess_xml_int(value_xml);
}

static PyObject *
postprocess_xml_date(const xmlChar *value_xml) {
  PyObject *callable =
    xmlStrchr(value_xml, (xmlChar)' ') ? parse_date_func : fromisoformat_func;
  PyObject *value_py = postprocess_xml_str(value_xml);
  PyObject *args[2] = {nullptr, value_py};
  PyObject *result = PyObject_Vectorcall(
    callable, args + 1, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, nullptr
  );
  Py_DECREF(value_py);
  return result;
}

typedef struct {
  const char *key;
  PyObject *(*func)(const xmlChar *);
} ValuePostprocessorItem;

static const ValuePostprocessorItem value_postprocessor_map[] = {
  {"changes_count", postprocess_xml_int}, {"changeset", postprocess_xml_int},
  {"closed_at", postprocess_xml_date},    {"comments_count", postprocess_xml_int},
  {"created_at", postprocess_xml_date},   {"date", postprocess_xml_date},
  {"ele", postprocess_xml_float},         {"id", postprocess_xml_int},
  {"lat", postprocess_xml_float},         {"lon", postprocess_xml_float},
  {"max_lat", postprocess_xml_float},     {"max_lon", postprocess_xml_float},
  {"min_lat", postprocess_xml_float},     {"min_lon", postprocess_xml_float},
  {"num_changes", postprocess_xml_int},   {"open", postprocess_xml_bool},
  {"pending", postprocess_xml_bool},      {"ref", postprocess_xml_int},
  {"time", postprocess_xml_date},         {"timestamp", postprocess_xml_date},
  {"uid", postprocess_xml_int},           {"updated_at", postprocess_xml_date},
  {"version", postprocess_xml_version},   {"visible", postprocess_xml_bool},
};

static int
postprocess_value_cmp(const void *key, const void *element) {
  return strcmp((const char *)key, ((const ValuePostprocessorItem *)element)->key);
}

static PyObject *
postprocess_value(const char *key, const xmlChar *value_xml) {
  ValuePostprocessorItem *item = bsearch(
    key, value_postprocessor_map,
    sizeof(value_postprocessor_map) / sizeof(ValuePostprocessorItem),
    sizeof(ValuePostprocessorItem), postprocess_value_cmp
  );
  return item ? item->func(value_xml) : postprocess_xml_str(value_xml);
}

#pragma endregion

static PyObject *
xml_parse(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyBytes_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  char *buffer;
  Py_ssize_t buffer_size;
  PyBytes_AsStringAndSize(args[0], &buffer, &buffer_size);
  assert(INT_MIN <= buffer_size && buffer_size <= INT_MAX);

  xmlTextReaderPtr reader = xmlReaderForMemory(
    buffer, buffer_size, nullptr, nullptr,
    XML_PARSE_NOCDATA | XML_PARSE_COMPACT | XML_PARSE_NO_XXE
  );
  // TODO: 2.14 XML_PARSE_NO_SYS_CATALOG

  if (UNLIKELY(!reader)) {
    const xmlError *error = xmlGetLastError();
    xmlResetLastError();
    return PyErr_Format(
      PyExc_ValueError, "Error initializing XML reader: %s",
      error && error->message ? error->message : "Unknown error"
    );
  }

  PyObject *stack = PyList_New(LIST_PREALLOC_SIZE);
  PyObject *attr_cache = PyDict_New();
  PyObject *text_key = nullptr;
  PyObject *parent_name = nullptr;
  PyObject *current_name = nullptr;
  PyObject *current_dict = nullptr;
  PyObject *current_list = nullptr;
  PyObject *result = nullptr;
  if (UNLIKELY(!stack || !attr_cache))
    goto fail;
  _PyVarObject_CAST(stack)->ob_size = 0;

  auto parse_ret = xmlTextReaderRead(reader);
  auto node_type = xmlTextReaderNodeType(reader);
  while (LIKELY(parse_ret == 1)) {
    switch (node_type) {
    case XML_READER_TYPE_ELEMENT: {
      if (LIKELY(current_dict != nullptr)) { // Push to stack
        PyObject *tuple = PyTuple_Pack(3, current_name, current_dict, current_list);
        if (UNLIKELY(!tuple))
          goto fail;

        auto append_result = PyList_Append(stack, tuple);
        Py_DECREF(tuple);
        if (UNLIKELY(append_result))
          goto fail;

        Py_DECREF(current_name);
        Py_DECREF(current_dict);
        Py_DECREF(current_list);
      }

      current_name =
        PyUnicode_FromString((const char *)xmlTextReaderConstLocalName(reader));
      current_dict = Py_None;
      current_list = Py_None;
      if (UNLIKELY(!current_name))
        goto fail;
      // TODO: prefer PyUnicode_InternFromString if defined to be
      // immortal https://github.com/python/cpython/issues/133260
      PyUnicode_InternInPlace(&current_name);
      break;
    }
    case XML_READER_TYPE_END_ELEMENT: {
      PyObject *current_result;
      if (current_dict == Py_None && current_list == Py_None)
        current_result = nullptr;
      else if (current_list == Py_None) {
        // Handle potential text-only case
        current_result = text_key && PyDict_GET_SIZE(current_dict) == 1
                           ? PyDict_GetItem(current_dict, text_key)
                           : nullptr;

        if (current_result) {
          Py_INCREF(current_result);
          Py_CLEAR(current_dict);
        } else {
          current_result = current_dict;
          current_dict = nullptr;
        }
      } else if (current_dict == Py_None) {
        current_result = current_list;
        current_list = nullptr;
      } else // current_dict != Py_None && current_list != Py_None
      {
        PyObject *items = PyDict_Items(current_dict);
        if (UNLIKELY(!items))
          goto fail;
        PyList_Extend(current_list, items);
        Py_DECREF(items);
        Py_CLEAR(current_dict);

        current_result = current_list;
        current_list = nullptr;
      }

      auto stack_size = PyList_GET_SIZE(stack);
      if (LIKELY(stack_size)) { // Pop from stack
        stack_size -= 1;
        _PyVarObject_CAST(stack)->ob_size = stack_size;
        PyObject *tuple = PyList_GET_ITEM(stack, stack_size);
        parent_name = PyTuple_GET_ITEM(tuple, 0);
        current_dict = PyTuple_GET_ITEM(tuple, 1);
        current_list = PyTuple_GET_ITEM(tuple, 2);
        Py_INCREF(parent_name);
        Py_INCREF(current_dict);
        Py_INCREF(current_list);
        Py_DECREF(tuple); // Pop after resize

        if (!current_result)
          goto merge_ok;

        // Append in "items" mode
        const char *current_name_c = PyUnicode_AsUTF8(current_name);
        if (in_set(
              current_name_c, sizeof(force_items_set) / sizeof(char *), force_items_set
            )) {
          if (current_list == Py_None) {
            current_list = PyList_New(LIST_PREALLOC_SIZE);
            if (UNLIKELY(!current_list)) {
              Py_DECREF(current_result);
              goto fail;
            }
            _PyVarObject_CAST(current_list)->ob_size = 0;
          }

          PyObject *tuple = PyTuple_Pack(2, current_name, current_result);
          Py_DECREF(current_result);
          if (UNLIKELY(!tuple))
            goto fail;

          auto append_result = PyList_Append(current_list, tuple);
          Py_DECREF(tuple);
          if (UNLIKELY(append_result))
            goto fail;

          goto merge_ok;
        }

        // Merge with existing value
        PyObject *existing_result = current_dict != Py_None
                                      ? PyDict_GetItem(current_dict, current_name)
                                      : nullptr;
        if (existing_result) {
          if (PyList_CheckExact(existing_result)) {
            auto append_result = PyList_Append(existing_result, current_result);
            Py_DECREF(current_result);
            if (UNLIKELY(append_result))
              goto fail;
          } else { // Upgrade to a list
            PyObject *list = PyList_New(LIST_PREALLOC_SIZE);
            if (UNLIKELY(!list)) {
              Py_DECREF(current_result);
              goto fail;
            }
            assert(LIST_PREALLOC_SIZE >= 2);
            _PyVarObject_CAST(list)->ob_size = 2;

            Py_INCREF(existing_result);
            PyList_SET_ITEM(list, 0, existing_result);
            PyList_SET_ITEM(list, 1, current_result);

            auto set_result = PyDict_SetItem(current_dict, current_name, list);
            Py_DECREF(list);
            if (UNLIKELY(set_result))
              goto fail;
          }

          goto merge_ok;
        }

        // Append new value
        if (current_dict == Py_None) {
          current_dict = PyDict_New();
          if (UNLIKELY(!current_dict)) {
            Py_DECREF(current_result);
            goto fail;
          }
        }

        // Optionally wrap in a list
        if (in_set(
              current_name_c, sizeof(force_list_set) / sizeof(char *), force_list_set
            )) {
          PyObject *list = PyList_New(LIST_PREALLOC_SIZE);
          if (UNLIKELY(!list)) {
            Py_DECREF(current_result);
            goto fail;
          }
          assert(LIST_PREALLOC_SIZE >= 1);
          _PyVarObject_CAST(list)->ob_size = 1;

          PyList_SET_ITEM(list, 0, current_result);
          current_result = list;
        }

        auto set_result = PyDict_SetItem(current_dict, current_name, current_result);
        Py_DECREF(current_result);
        if (UNLIKELY(set_result))
          goto fail;

merge_ok:
        Py_DECREF(current_name);
        current_name = parent_name;
        parent_name = nullptr;
      } else { // Finished parsing, wrap in a dict
        result = PyDict_New();
        if (UNLIKELY(!result))
          goto fail;

        auto set_result = PyDict_SetItem(result, current_name, current_result);
        Py_DECREF(current_result);
        if (UNLIKELY(set_result))
          goto fail;
        goto ok;
      }
      break;
    }
    case XML_READER_TYPE_ATTRIBUTE:
    case XML_READER_TYPE_TEXT: {
      if (current_dict == Py_None) {
        current_dict = PyDict_New();
        if (UNLIKELY(!current_dict))
          goto fail;
      }

      const char *postprocess_key =
        node_type == XML_READER_TYPE_ATTRIBUTE
          ? (const char *)xmlTextReaderConstLocalName(reader)
          : PyUnicode_AsUTF8(current_name);

      PyObject *set_key;
      if (node_type == XML_READER_TYPE_ATTRIBUTE) {
        set_key = PyDict_GetItemString(attr_cache, postprocess_key);
        if (!set_key) { // Cache miss
          set_key = PyUnicode_FromFormat("@%s", postprocess_key);
          if (UNLIKELY(!set_key))
            goto fail;

          if (UNLIKELY(PyDict_SetItemString(attr_cache, postprocess_key, set_key))) {
            Py_DECREF(set_key);
            goto fail;
          }
        } else { // Cache hit
          Py_INCREF(set_key);
        }
      } else // XML_READER_TYPE_TEXT
      {
        if (UNLIKELY(!text_key)) {
          text_key = PyUnicode_InternFromString("#text");
          if (UNLIKELY(!text_key))
            goto fail;
        }
        set_key = text_key;
        // TODO: remove ref count and cleanup if immortal
        // https://github.com/python/cpython/issues/133260
      }

      const xmlChar *value_xml = xmlTextReaderConstValue(reader);
      PyObject *value = postprocess_value(postprocess_key, value_xml);
      if (UNLIKELY(!value)) {
        if (set_key != text_key)
          Py_DECREF(set_key);
        PyErr_Format(
          PyExc_ValueError, "Failed to postprocess '%s' value: %s", postprocess_key,
          value_xml
        );
        goto fail;
      }

      auto set_result = PyDict_SetItem(current_dict, set_key, value);
      if (set_key != text_key)
        Py_DECREF(set_key);
      Py_DECREF(value);
      if (UNLIKELY(set_result))
        goto fail;
      break;
    }
    }

    if (node_type == XML_READER_TYPE_ELEMENT ||
        node_type == XML_READER_TYPE_ATTRIBUTE) {
      parse_ret = xmlTextReaderMoveToNextAttribute(reader);
      if (parse_ret) // Found or error
      {
        node_type = XML_READER_TYPE_ATTRIBUTE;
        continue;
      }

      // Simulate XML_READER_TYPE_END_ELEMENT for self-closing tags
      if (node_type == XML_READER_TYPE_ATTRIBUTE)
        xmlTextReaderMoveToElement(reader);
      if (xmlTextReaderIsEmptyElement(reader)) {
        parse_ret = 1;
        node_type = XML_READER_TYPE_END_ELEMENT;
        continue;
      }
    }
    parse_ret = xmlTextReaderRead(reader);
    node_type = xmlTextReaderNodeType(reader);
  }

  if (UNLIKELY(parse_ret < 0)) {
    const xmlError *error = xmlGetLastError();
    PyErr_Format(
      PyExc_ValueError, "Error parsing XML: %s",
      error && error->message ? error->message : "Unknown error"
    );
    goto fail;
  }

ok:
  if (UNLIKELY(PyList_GET_SIZE(stack) || (!result && current_dict))) {
    PyErr_SetString(PyExc_AssertionError, "Stack is not empty after parsing");
    goto fail;
  }
  if (UNLIKELY(!result)) {
    PyErr_SetString(PyExc_ValueError, "Document is empty");
    goto fail;
  }

  if (false) {
fail:
    result = nullptr;
  }

  Py_XDECREF(stack);
  Py_XDECREF(attr_cache);
  Py_XDECREF(text_key);
  Py_XDECREF(parent_name);
  Py_XDECREF(current_name);
  Py_XDECREF(current_dict);
  Py_XDECREF(current_list);
  xmlFreeTextReader(reader);
  return result;
}

static PyMethodDef methods[] = {
  {"xml_parse", _PyCFunction_CAST(xml_parse), METH_FASTCALL, nullptr},
  {nullptr, nullptr, 0, nullptr},
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "optimized.xml_parse",
  nullptr,
  -1,
  methods,
  nullptr,
  nullptr,
  nullptr,
  nullptr
};

PyMODINIT_FUNC
PyInit_xml_parse(void) {
  PyObject *datetime_module = PyImport_ImportModule("datetime");
  PyObject *datetime_class = PyObject_GetAttrString(datetime_module, "datetime");
  fromisoformat_func = PyObject_GetAttrString(datetime_class, "fromisoformat");

  PyObject *date_utils_module = PyImport_ImportModule("app.lib.date_utils");
  parse_date_func = PyObject_GetAttrString(date_utils_module, "parse_date");

  return PyModule_Create(&module);
}
