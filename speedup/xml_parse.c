#include "libxml/xmlreader.h"
#include "libxml/xmlstring.h"
#include <Python.h>
#include <object.h>

#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)
#define PyScoped PyObject *__attribute__((cleanup(Py_XDECREFP)))

constexpr Py_ssize_t LIST_PREALLOC_SIZE = 8;
constexpr size_t STACK_SIZE = 10;

static PyObject *fromisoformat_func;
static PyObject *parse_date_func;
static PyObject *text_key;

static inline void
Py_XDECREFP(PyObject **ptr) {
  Py_XDECREF(*ptr);
}

static inline void
xmlFreeTextReaderPtr(xmlTextReaderPtr *ptr) {
  xmlFreeTextReader(*ptr);
}

#pragma region Stack

typedef struct {
  PyObject *name;
  PyObject *dict;
  PyObject *list;
} StackFrame;

typedef struct {
  size_t depth;
  StackFrame frames[STACK_SIZE];
} Stack;

static inline bool
stack_push(Stack *stack, PyObject *name, PyObject *dict, PyObject *list) {
  if (UNLIKELY(stack->depth >= STACK_SIZE)) {
    PyErr_Format(
      PyExc_RecursionError, "XML nesting depth exceeded limit of %zu", STACK_SIZE
    );
    return false;
  }

  StackFrame *frame = &stack->frames[stack->depth++];
  frame->name = name;
  frame->dict = dict;
  frame->list = list;
  return true;
}

static inline bool
stack_pop(Stack *stack, PyObject **name, PyObject **dict, PyObject **list) {
  if (UNLIKELY(!stack->depth)) {
    PyErr_SetString(PyExc_AssertionError, "Stack is empty");
    return false;
  }

  StackFrame *frame = &stack->frames[--stack->depth];
  *name = frame->name;
  *dict = frame->dict;
  *list = frame->list;
  return true;
}

static inline void
stack_cleanup(Stack *stack) {
  while (stack->depth) {
    StackFrame *frame = &stack->frames[--stack->depth];
    Py_DECREF(frame->name);
    Py_DECREF(frame->dict);
    Py_DECREF(frame->list);
  }
}

#pragma endregion
#pragma region StringCache

typedef struct {
  const char *key;
  PyObject *value;
} StringCacheEntry;

static inline PyObject *
get_tag_name(StringCacheEntry **cache_ptr, const char *tag_name) {
  StringCacheEntry *cache = *cache_ptr;
  PyObject *cached = shget(cache, tag_name);

  // Cache hit
  if (cached)
    return cached;

  // Cache miss
  PyObject *tag_obj = PyUnicode_FromString(tag_name);
  if (UNLIKELY(!tag_obj))
    return nullptr;

  shput(cache, tag_name, tag_obj);
  *cache_ptr = cache;
  return tag_obj;
}

static inline PyObject *
get_attr_key(StringCacheEntry **cache_ptr, const char *attr_name) {
  StringCacheEntry *cache = *cache_ptr;
  PyObject *cached = shget(cache, attr_name);

  // Cache hit
  if (cached)
    return cached;

  // Cache miss
  PyObject *prefixed_key = PyUnicode_FromFormat("@%s", attr_name);
  if (UNLIKELY(!prefixed_key))
    return nullptr;

  shput(cache, attr_name, prefixed_key);
  *cache_ptr = cache;
  return prefixed_key;
}

static void
cache_cleanup(StringCacheEntry **cache_ptr) {
  StringCacheEntry *cache = *cache_ptr;
  if (LIKELY(cache != nullptr)) {
    for (auto i = 0; i < shlen(cache); i++)
      Py_DECREF(cache[i].value);
    shfree(cache);
  }
}

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
  PyScoped value_py = postprocess_xml_str(value_xml);
  PyObject *args[] = {nullptr, value_py};
  PyObject *result = PyObject_Vectorcall(
    callable, args + 1, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, nullptr
  );
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

  xmlTextReaderPtr __attribute__((cleanup(xmlFreeTextReaderPtr))) reader =
    xmlReaderForMemory(
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

  Stack __attribute__((cleanup(stack_cleanup))) stack = {};
  StringCacheEntry *__attribute__((cleanup(cache_cleanup))) tag_cache;
  sh_new_arena(tag_cache);
  StringCacheEntry *__attribute__((cleanup(cache_cleanup))) attr_cache;
  sh_new_arena(attr_cache);

  PyScoped parent_name = nullptr;
  PyScoped current_name = nullptr;
  PyScoped current_dict = nullptr;
  PyScoped current_list = nullptr;
  PyObject *result = nullptr;

  auto parse_ret = xmlTextReaderRead(reader);
  auto node_type = xmlTextReaderNodeType(reader);
  while (LIKELY(parse_ret == 1)) {
    switch (node_type) {
    case XML_READER_TYPE_ELEMENT: {
      // Push to stack
      if (LIKELY(current_dict != nullptr) &&
          UNLIKELY(!stack_push(&stack, current_name, current_dict, current_list)))
        return nullptr;

      current_name =
        get_tag_name(&tag_cache, (const char *)xmlTextReaderConstLocalName(reader));
      current_dict = Py_None;
      current_list = Py_None;
      if (UNLIKELY(!current_name))
        return nullptr;
      Py_INCREF(current_name);
      break;
    }
    case XML_READER_TYPE_END_ELEMENT: {
      PyScoped current_result;

      if (current_dict == Py_None && current_list == Py_None)
        current_result = nullptr;
      else if (current_list == Py_None) {
        // Handle potential text-only case
        current_result = PyDict_GET_SIZE(current_dict) == 1
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
      } else { // current_dict != Py_None && current_list != Py_None
        PyScoped items = PyDict_Items(current_dict);
        if (UNLIKELY(!items || PyList_Extend(current_list, items)))
          return nullptr;

        Py_CLEAR(current_dict);
        current_result = current_list;
        current_list = nullptr;
      }

      if (LIKELY(stack.depth)) {
        // Pop from stack
        if (UNLIKELY(!stack_pop(&stack, &parent_name, &current_dict, &current_list)))
          return nullptr;
        if (!current_result)
          goto merge_ok;

        // Append in "items" mode
        const char *current_name_c = PyUnicode_AsUTF8(current_name);
        if (UNLIKELY(!current_name_c))
          return nullptr;
        if (in_set(
              current_name_c, sizeof(force_items_set) / sizeof(char *), force_items_set
            )) {
          if (current_list == Py_None) {
            current_list = PyList_New(LIST_PREALLOC_SIZE);
            if (UNLIKELY(!current_list))
              return nullptr;
            Py_SET_SIZE(current_list, 0);
          }

          PyScoped tuple = PyTuple_Pack(2, current_name, current_result);
          if (UNLIKELY(!tuple || PyList_Append(current_list, tuple)))
            return nullptr;

          goto merge_ok;
        }

        // Merge with existing value
        PyObject *existing_result = current_dict != Py_None
                                      ? PyDict_GetItem(current_dict, current_name)
                                      : nullptr;
        if (existing_result) {
          if (PyList_CheckExact(existing_result)) {
            if (UNLIKELY(PyList_Append(existing_result, current_result)))
              return nullptr;
          } else {
            // Upgrade to a list
            PyScoped list = PyList_New(LIST_PREALLOC_SIZE);
            if (UNLIKELY(!list))
              return nullptr;

            static_assert(LIST_PREALLOC_SIZE >= 2);
            Py_SET_SIZE(list, 2);
            Py_INCREF(existing_result);
            Py_INCREF(current_result);
            PyList_SET_ITEM(list, 0, existing_result);
            PyList_SET_ITEM(list, 1, current_result);

            if (UNLIKELY(PyDict_SetItem(current_dict, current_name, list)))
              return nullptr;
          }

          goto merge_ok;
        }

        // Append new value
        if (current_dict == Py_None) {
          current_dict = PyDict_New();
          if (UNLIKELY(!current_dict))
            return nullptr;
        }

        // Optionally wrap in a list
        if (in_set(
              current_name_c, sizeof(force_list_set) / sizeof(char *), force_list_set
            )) {
          PyObject *list = PyList_New(LIST_PREALLOC_SIZE);
          if (UNLIKELY(!list))
            return nullptr;

          static_assert(LIST_PREALLOC_SIZE >= 1);
          Py_SET_SIZE(list, 1);
          PyList_SET_ITEM(list, 0, current_result);
          current_result = list;
        }

        if (UNLIKELY(PyDict_SetItem(current_dict, current_name, current_result)))
          return nullptr;

merge_ok:
        Py_SETREF(current_name, parent_name);
        parent_name = nullptr;
      } else {
        // Finished parsing, wrap in a dict
        result = PyDict_New();
        if (UNLIKELY(!result || PyDict_SetItem(result, current_name, current_result)))
          return nullptr;

        goto ok;
      }
      break;
    }
    case XML_READER_TYPE_ATTRIBUTE:
    case XML_READER_TYPE_TEXT: {
      if (current_dict == Py_None) {
        current_dict = PyDict_New();
        if (UNLIKELY(!current_dict))
          return nullptr;
      }

      const char *postprocess_key;
      if (node_type == XML_READER_TYPE_ATTRIBUTE)
        postprocess_key = (const char *)xmlTextReaderConstLocalName(reader);
      else {
        postprocess_key = PyUnicode_AsUTF8(current_name);
        if (UNLIKELY(!postprocess_key))
          return nullptr;
      }

      const xmlChar *value_xml = xmlTextReaderConstValue(reader);
      PyScoped value = postprocess_value(postprocess_key, value_xml);
      if (UNLIKELY(!value)) {
        PyErr_Format(
          PyExc_ValueError, "Failed to postprocess '%s' value: %s", postprocess_key,
          value_xml
        );
        return nullptr;
      }

      PyObject *set_key;
      if (node_type == XML_READER_TYPE_ATTRIBUTE) {
        set_key = get_attr_key(&attr_cache, postprocess_key);
        if (UNLIKELY(!set_key))
          return nullptr;
      } else { // XML_READER_TYPE_TEXT
        set_key = text_key;
      }

      if (UNLIKELY(PyDict_SetItem(current_dict, set_key, value)))
        return nullptr;
      break;
    }
    }

    // Iterate to the next node.
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
    return nullptr;
  }

ok:
  if (UNLIKELY(stack.depth || (!result && current_dict))) {
    PyErr_SetString(PyExc_AssertionError, "Stack is not empty after parsing");
    return nullptr;
  }
  if (UNLIKELY(!result)) {
    PyErr_SetString(PyExc_ValueError, "Document is empty");
    return nullptr;
  }
  return result;
}

static PyMethodDef methods[] = {
  {"xml_parse", _PyCFunction_CAST(xml_parse), METH_FASTCALL, nullptr},
  {nullptr, nullptr, 0, nullptr},
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "speedup.xml_parse",
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
  PyScoped datetime_module = PyImport_ImportModule("datetime");
  PyScoped datetime_class = PyObject_GetAttrString(datetime_module, "datetime");
  fromisoformat_func = PyObject_GetAttrString(datetime_class, "fromisoformat");

  PyScoped date_utils_module = PyImport_ImportModule("app.lib.date_utils");
  parse_date_func = PyObject_GetAttrString(date_utils_module, "parse_date");

  text_key = PyUnicode_InternFromString("#text");

  return PyModule_Create(&module);
}
