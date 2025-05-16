#include <Python.h>
#include <stdlib.h>
#include "libxml/xmlreader.h"
#include "libxml/xmlstring.h"

#pragma region Globals

static PyObject *fromisoformat_func = NULL;
static PyObject *parse_date_func = NULL;
static xmlTextReaderPtr reader = {};

#pragma endregion
#pragma region Sets

// These arrays MUST be sorted alphabetically for bsearch to work
static const char *force_sequence_root_set[] = {
    "bounds", "create", "delete", "modify", "node", "relation", "way"};
static const char *force_list_set[] = {
    "comment", "gpx_file", "member", "nd", "note", "preference", "tag", "trk", "trkpt", "trkseg"};

[[unsequenced]]
static int in_set_cmp(const void *key, const void *element)
{
    return strcmp((const char *)key, *(const char **)element);
}

[[unsequenced]]
static bool in_set(const char *str, size_t set_size, const char *set[static set_size])
{
    return bsearch(str, set, set_size, sizeof(char *), in_set_cmp) != NULL;
}

#pragma endregion
#pragma region Postprocessors

static PyObject *postprocess_xml_str(const xmlChar *value_xml)
{
    return PyUnicode_FromString((const char *)value_xml);
}

static PyObject *postprocess_xml_int(const xmlChar *value_xml)
{
    errno = 0;
    long long value = strtoll((const char *)value_xml, NULL, 10);
    return (value != 0 || errno == 0) ? PyLong_FromLongLong(value) : NULL;
}

static PyObject *postprocess_xml_float(const xmlChar *value_xml)
{
    errno = 0;
    double value = strtod((const char *)value_xml, NULL);
    return (value != 0 || errno == 0) ? PyFloat_FromDouble(value) : NULL;
}

static PyObject *postprocess_xml_bool(const xmlChar *value_xml)
{
    if (xmlStrEqual(value_xml, (const xmlChar *)"true"))
    {
        Py_RETURN_TRUE;
    }
    if (xmlStrEqual(value_xml, (const xmlChar *)"false"))
    {
        Py_RETURN_FALSE;
    }
    return NULL;
}

static PyObject *postprocess_xml_version(const xmlChar *value_xml)
{
    return xmlStrchr(value_xml, (xmlChar)'.')
               ? postprocess_xml_float(value_xml)
               : postprocess_xml_int(value_xml);
}

static PyObject *postprocess_xml_date(const xmlChar *value_xml)
{
    PyObject *callable = xmlStrchr(value_xml, (xmlChar)' ') ? parse_date_func : fromisoformat_func;
    PyObject *value_py = postprocess_xml_str(value_xml);
    PyObject *args[2] = {NULL, value_py};
    PyObject *result = PyObject_Vectorcall(callable, args + 1, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
    Py_DECREF(value_py);
    return result;
}

typedef PyObject *(*ValuePostprocessorFunc)(const xmlChar *);
typedef struct
{
    const char *key;
    ValuePostprocessorFunc func;
} ValuePostprocessorItem;

static const ValuePostprocessorItem value_postprocessor_map[] = {
    {"changes_count", postprocess_xml_int},
    {"changeset", postprocess_xml_int},
    {"closed_at", postprocess_xml_date},
    {"comments_count", postprocess_xml_int},
    {"created_at", postprocess_xml_date},
    {"date", postprocess_xml_date},
    {"ele", postprocess_xml_float},
    {"id", postprocess_xml_int},
    {"lat", postprocess_xml_float},
    {"lon", postprocess_xml_float},
    {"max_lat", postprocess_xml_float},
    {"max_lon", postprocess_xml_float},
    {"min_lat", postprocess_xml_float},
    {"min_lon", postprocess_xml_float},
    {"num_changes", postprocess_xml_int},
    {"open", postprocess_xml_bool},
    {"pending", postprocess_xml_bool},
    {"ref", postprocess_xml_int},
    {"time", postprocess_xml_date},
    {"timestamp", postprocess_xml_date},
    {"uid", postprocess_xml_int},
    {"updated_at", postprocess_xml_date},
    {"version", postprocess_xml_version},
    {"visible", postprocess_xml_bool},
};

[[unsequenced]]
static int postprocess_value_cmp(const void *key, const void *element)
{
    return strcmp((const char *)key, ((const ValuePostprocessorItem *)element)->key);
}

static PyObject *postprocess_value(const char *key, const xmlChar *value_xml)
{
    const ValuePostprocessorItem *item = bsearch(key, value_postprocessor_map, sizeof(value_postprocessor_map) / sizeof(ValuePostprocessorItem), sizeof(ValuePostprocessorItem), postprocess_value_cmp);
    return item != NULL ? item->func(value_xml) : postprocess_xml_str(value_xml);
}

#pragma endregion

static int add_child_to_parent_py_obj(PyObject *parent_py_obj, PyObject *key_py_unicode, PyObject *child_obj, const char *child_local_name_c_str)
{
    int result = -1;

    if (PyDict_Check(parent_py_obj))
    {
        PyObject *existing_val = PyDict_GetItem(parent_py_obj, key_py_unicode);
        if (existing_val)
        {
            if (PyList_Check(existing_val))
            {
                if (PyList_Append(existing_val, child_obj) == 0)
                    result = 0;
            }
            else
            {
                PyObject *new_list = PyList_New(2);
                if (new_list)
                {
                    Py_INCREF(existing_val);
                    PyList_SET_ITEM(new_list, 0, existing_val);
                    Py_INCREF(child_obj);
                    PyList_SET_ITEM(new_list, 1, child_obj);
                    if (PyDict_SetItem(parent_py_obj, key_py_unicode, new_list) == 0)
                        result = 0;
                    Py_DECREF(new_list);
                }
            }
        }
        else
        {
            if (is_string_in_set_c(child_local_name_c_str, force_list_elements_c, FORCE_LIST_COUNT))
            {
                PyObject *new_list = PyList_New(1);
                if (new_list)
                {
                    Py_INCREF(child_obj);
                    PyList_SET_ITEM(new_list, 0, child_obj);
                    if (PyDict_SetItem(parent_py_obj, key_py_unicode, new_list) == 0)
                        result = 0;
                    Py_DECREF(new_list);
                }
            }
            else
            {
                if (PyDict_SetItem(parent_py_obj, key_py_unicode, child_obj) == 0)
                    result = 0;
            }
        }
    }
    else if (PyList_Check(parent_py_obj))
    {
        PyObject *tuple_item = PyTuple_Pack(2, key_py_unicode, child_obj);
        if (tuple_item)
        {
            if (PyList_Append(parent_py_obj, tuple_item) == 0)
                result = 0;
            Py_DECREF(tuple_item);
        }
    }
    else
    {
        PyErr_SetString(PyExc_TypeError, "Internal error: Parent container in add_child_to_parent is not Dict or List.");
    }
    return result;
}

static PyObject *parse(PyObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (PyVectorcall_NARGS(nargs) != 1)
    {
        return PyErr_Format(PyExc_TypeError, "parse(bytes, /) takes exactly 1 argument");
    }

    const char *buffer;
    const Py_ssize_t buffer_size;
    PyBytes_AsStringAndSize(args[0], &buffer, &buffer_size);
    assert(INT_MIN <= buffer_size && buffer_size <= INT_MAX);

    if (xmlReaderNewMemory(
            reader, buffer, buffer_size, NULL, NULL,
            XML_PARSE_NOCDATA | XML_PARSE_COMPACT | XML_PARSE_NO_XXE | XML_PARSE_NO_SYS_CATALOG))
    {
        return PyErr_Format(PyExc_RuntimeError, "Failed to setup an xmltextReader");
    }

    PyObject *stack = PyList_New(6);
    PyObject *attr_cache = PyDict_New();
    PyObject *text_key = PyUnicode_InternFromString('#text');
    PyObject *current_name = NULL;
    PyObject *current = NULL;
    PyObject *current_seq = NULL;
    PyObject *current_text = NULL;
    PyObject *result = NULL;

    if (!stack || !attr_cache)
    {
        PyErr_Format(PyExc_RuntimeError, "Failed to allocate stack and attr_cache");
        goto fail;
    }

    // Free stack pre-allocation
    ((PyVarObject *)stack)->ob_size = 0;

    for (int parse_ret = xmlTextReaderRead(reader); parse_ret == 1; parse_ret = xmlTextReaderRead(reader))
    {
        const int node_type = xmlTextReaderNodeType(reader);
        switch (node_type)
        {
        case XML_READER_TYPE_ELEMENT:
        {
            if (current)
            {
                PyObject *tuple = PyTuple_Pack(4, current_name, current, current_seq, current_text);
                Py_CLEAR(current_name);
                Py_CLEAR(current);
                Py_CLEAR(current_seq);
                Py_CLEAR(current_text);
                int append_result = PyList_Append(stack, tuple);
                Py_DECREF(tuple);
                if (append_result)
                {
                    PyErr_Format(PyExc_RuntimeError, "Failed to grow stack");
                    goto fail;
                }
            }

            current_name = PyUnicode_FromString(xmlTextReaderConstLocalName(reader));
            current = PyDict_New();
            current_seq = Py_None;
            current_text = Py_None;
            if (!current_name || !current)
            {
                Py_CLEAR(current_name);
                Py_CLEAR(current);
                PyErr_Format(PyExc_RuntimeError, "Failed to allocate current and current_name");
                goto fail;
            }
            break;
        }
        case XML_READER_TYPE_END_ELEMENT:
        {
            assert(current);
            Py_CLEAR(current_name);
            Py_CLEAR(current);
            Py_CLEAR(current_seq);
            Py_CLEAR(current_text);

            Py_ssize_t stack_size = ((PyVarObject *)stack)->ob_size;
            if (stack_size)
            {
                stack_size -= 1;
                ((PyVarObject *)stack)->ob_size = stack_size;
                PyObject *tuple = PyList_GET_ITEM(stack, stack_size);
                current_name = PyTuple_GET_ITEM(tuple, 0);
                current = PyTuple_GET_ITEM(tuple, 1);
                current_seq = PyTuple_GET_ITEM(tuple, 2);
                current_text = PyTuple_GET_ITEM(tuple, 3);
                Py_INCREF(current_name);
                Py_INCREF(current);
                Py_INCREF(current_seq);
                Py_INCREF(current_text);
                Py_DECREF(tuple); // Pop
            }
            else
            {
                // This is the root element, store the result and we're done
                current = NULL;
                current_name = NULL;
            }
            break;
        }
        case XML_READER_TYPE_ATTRIBUTE:
        case XML_READER_TYPE_TEXT:
        {
            assert(current);
            const xmlChar *value_xml = xmlTextReaderConstValue(reader);
            if (!value_xml || value_xml[0] == '\0')
                break; // Skip empty values

            const char *postprocess_key;
            const PyObject *set_key;
            if (node_type == XML_READER_TYPE_ATTRIBUTE)
            {
                postprocess_key = xmlTextReaderConstLocalName(reader);
                set_key = PyDict_GetItemString(attr_cache, postprocess_key);
                if (!set_key)
                {
                    set_key = PyUnicode_FromFormat("@%s", postprocess_key);
                    if (!set_key)
                    {
                        PyErr_Format(PyExc_RuntimeError, "Failed to create '@%s' key", postprocess_key);
                        goto fail;
                    }
                    if (PyDict_SetItemString(attr_cache, postprocess_key, set_key))
                    {
                        Py_DECREF(set_key);
                        PyErr_Format(PyExc_RuntimeError, "Failed to set '@%s' key in cache", postprocess_key);
                        goto fail;
                    }
                }
            }
            else
            {
                postprocess_key = PyUnicode_AsUTF8(current_name);
                set_key = text_key;
            }

            const PyObject *value = postprocess_value(postprocess_key, value_xml);
            if (!value)
            {
                Py_DECREF(set_key);
                PyErr_Format(PyExc_ValueError, "Invalid postprocess '%s' value: %s", postprocess_key, value_xml);
                goto fail;
            }

            if (PyDict_CheckExact(current))
            {
                int set_result = PyDict_SetItem(current, set_key, value);
                Py_DECREF(set_key);
                Py_DECREF(value);
                if (set_result)
                {
                    PyErr_Format(PyExc_RuntimeError, "Failed to set '%s' key", postprocess_key);
                    goto fail;
                }
            }
            else // PyList
            {
                PyObject *tuple = PyTuple_Pack(2, set_key, value);
                Py_DECREF(set_key);
                Py_DECREF(value);
                if (!tuple)
                    goto fail;

                int append_result = PyList_Append(current, tuple);
                Py_DECREF(tuple);
                if (append_result)
                {
                    PyErr_Format(PyExc_RuntimeError, "Failed to append '%s' key", postprocess_key);
                    goto fail;
                }
            }
            break;
        }
        }
    }

fail:
    Py_XDECREF(stack);
    Py_XDECREF(attr_cache);
    Py_XDECREF(current_name);
    Py_XDECREF(current);
    Py_XDECREF(current_seq);
    Py_XDECREF(current_text);
    return result;

    const char *xml_data_bytes = NULL;
    Py_ssize_t xml_data_len = 0;
    long size_limit_long = -1;
    static char *kwlist[] = {"xml_bytes", "size_limit", NULL};

    xmlTextReaderPtr reader = NULL;
    PyObject *result_root_key_py = NULL;
    PyObject *result_root_value_py = NULL;
    PyObject *parse_stack_py = NULL;
    PyObject *attr_cache_py = NULL;
    PyObject *current_local_name_py = NULL;
    PyObject *current_element_obj_py = NULL;
    PyObject *py_attr_value_processed = NULL;
    PyObject *py_attr_qname_for_cache = NULL;
    PyObject *py_prefixed_key_for_dict = NULL;
    PyObject *stack_frame_py = NULL;
    PyObject *popped_frame_py = NULL;
    PyObject *text_key_py = NULL;
    PyObject *py_text_obj = NULL;
    PyObject *existing_text_py = NULL;
    PyObject *new_text_py = NULL;
    PyObject *attr_tuple_py = NULL;
    xmlChar *trimmed_value_xml = NULL;

    int parse_ret = -1;

    PyArg_ParseTuple

        if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s#|l:parse", kwlist,
                                         &xml_data_bytes, &xml_data_len, &size_limit_long))
    {
        return NULL;
    }

    int reader_options = XML_PARSER_NONET | XML_PARSER_NOENT | XML_PARSER_RECOVER;

    xmlReaderNewMemory reader = xmlNewTextReaderMemory(xml_data_bytes, (int)xml_data_len, NULL, NULL, reader_options);
    if (reader == NULL)
    {
        PyErr_SetString(PyExc_RuntimeError, "Failed to create XmlTextReader.");
        goto error_cleanup;
    }

    parse_stack_py = PyList_New(0);
    if (!parse_stack_py)
        goto error_cleanup;

    attr_cache_py = PyDict_New();
    if (!attr_cache_py)
        goto error_cleanup;

    parse_ret = xmlTextReaderRead(reader);
    while (parse_ret == 1)
    {
        int node_type = xmlTextReaderNodeType(reader);
        const char *current_local_name_c = get_local_name_from_reader_c(reader);

        PyObject *current_parent_container_py = NULL;
        PyObject *current_parent_local_name_py = NULL;

        if (PyList_Size(parse_stack_py) > 0)
        {
            PyObject *top_tuple = PyList_GetItem(parse_stack_py, PyList_Size(parse_stack_py) - 1);
            if (top_tuple && PyTuple_Check(top_tuple) && PyTuple_Size(top_tuple) == 2)
            {
                current_parent_container_py = PyTuple_GetItem(top_tuple, 0);
                current_parent_local_name_py = PyTuple_GetItem(top_tuple, 1);
            }
            else
            {
                PyErr_SetString(PyExc_SystemError, "Internal parser stack corruption.");
                goto error_cleanup;
            }
        }

        if (node_type == XML_READER_TYPE_ELEMENT)
        {
            current_local_name_py = PyUnicode_FromString(current_local_name_c);
            if (!current_local_name_py)
                goto error_cleanup;

            if (is_string_in_set_c(current_local_name_c, force_sequence_root_elements_c, FORCE_SEQUENCE_ROOT_COUNT))
            {
                current_element_obj_py = PyList_New(0);
            }
            else
            {
                current_element_obj_py = PyDict_New();
            }
            if (!current_element_obj_py)
                goto error_cleanup;

            if (current_parent_container_py)
            {
                if (add_child_to_parent_py_obj(current_parent_container_py, current_local_name_py, current_element_obj_py, current_local_name_c) < 0)
                {
                    goto error_cleanup;
                }
            }
            else
            {
                Py_XDECREF(result_root_key_py);
                Py_XDECREF(result_root_value_py);
                result_root_key_py = current_local_name_py;
                Py_INCREF(result_root_key_py);
                result_root_value_py = current_element_obj_py;
                Py_INCREF(result_root_value_py);
            }

            if (xmlTextReaderHasAttributes(reader))
            {
                if (xmlTextReaderMoveToFirstAttribute(reader) == 1)
                {
                    do
                    {
                        const char *attr_qname_c = (const char *)xmlTextReaderConstName(reader);
                        const char *attr_local_name_c = get_local_name_from_reader_c(reader);
                        const xmlChar *attr_value_xml = xmlTextReaderConstValue(reader);

                        py_attr_value_processed = apply_value_postprocessor_c(attr_local_name_c, attr_value_xml);
                        if (!py_attr_value_processed)
                            goto error_cleanup;

                        py_attr_qname_for_cache = PyUnicode_FromString(attr_qname_c);
                        if (!py_attr_qname_for_cache)
                            goto error_cleanup;

                        py_prefixed_key_for_dict = PyDict_GetItem(attr_cache_py, py_attr_qname_for_cache);
                        if (py_prefixed_key_for_dict)
                        {
                            Py_INCREF(py_prefixed_key_for_dict);
                        }
                        else
                        {
                            size_t qname_len = strlen(attr_qname_c);
                            char *temp_prefixed_name_c = (char *)PyMem_Malloc(qname_len + 2);
                            if (!temp_prefixed_name_c)
                            {
                                PyErr_NoMemory();
                                goto error_cleanup;
                            }
                            sprintf(temp_prefixed_name_c, "@%s", attr_qname_c);
                            py_prefixed_key_for_dict = PyUnicode_FromString(temp_prefixed_name_c);
                            PyMem_Free(temp_prefixed_name_c);
                            if (!py_prefixed_key_for_dict)
                                goto error_cleanup;

                            if (PyDict_SetItem(attr_cache_py, py_attr_qname_for_cache, py_prefixed_key_for_dict) < 0)
                                goto error_cleanup;
                        }
                        Py_DECREF(py_attr_qname_for_cache);
                        py_attr_qname_for_cache = NULL;

                        if (PyDict_Check(current_element_obj_py))
                        {
                            if (PyDict_SetItem(current_element_obj_py, py_prefixed_key_for_dict, py_attr_value_processed) < 0)
                                goto error_cleanup;
                        }
                        else if (PyList_Check(current_element_obj_py))
                        {
                            attr_tuple_py = PyTuple_Pack(2, py_prefixed_key_for_dict, py_attr_value_processed);
                            if (!attr_tuple_py)
                                goto error_cleanup;
                            if (PyList_Append(current_element_obj_py, attr_tuple_py) < 0)
                                goto error_cleanup;
                            Py_DECREF(attr_tuple_py);
                            attr_tuple_py = NULL;
                        }
                        Py_DECREF(py_prefixed_key_for_dict);
                        py_prefixed_key_for_dict = NULL;
                        Py_DECREF(py_attr_value_processed);
                        py_attr_value_processed = NULL;

                    } while (xmlTextReaderMoveToNextAttribute(reader) == 1);
                    xmlTextReaderMoveToElement(reader);
                }
            }

            if (!xmlTextReaderIsEmptyElement(reader))
            {
                stack_frame_py = PyTuple_Pack(2, current_element_obj_py, current_local_name_py);
                if (!stack_frame_py)
                    goto error_cleanup;
                if (PyList_Append(parse_stack_py, stack_frame_py) < 0)
                    goto error_cleanup;
                Py_DECREF(stack_frame_py);
                stack_frame_py = NULL;
            }
            Py_DECREF(current_local_name_py);
            current_local_name_py = NULL;
            Py_DECREF(current_element_obj_py);
            current_element_obj_py = NULL;
        }
        else if (node_type == XML_READER_TYPE_END_ELEMENT)
        {
            if (PyList_Size(parse_stack_py) > 0)
            {
                popped_frame_py = PyList_Pop(parse_stack_py, PyList_Size(parse_stack_py) - 1);
                if (!popped_frame_py)
                    goto error_cleanup;
                Py_DECREF(popped_frame_py);
                popped_frame_py = NULL;
            }
        }
        else if (node_type == XML_READER_TYPE_TEXT || node_type == XML_READER_TYPE_CDATA)
        {
            if (current_parent_container_py && current_parent_local_name_py)
            {
                const xmlChar *value_xml = xmlTextReaderConstValue(reader);
                if (value_xml && xmlStrlen(value_xml) > 0)
                {
                    trimmed_value_xml = trim_xml_string_c(value_xml);
                    if (trimmed_value_xml && xmlStrlen(trimmed_value_xml) > 0)
                    {
                        const char *parent_local_name_c = PyUnicode_AsUTF8(current_parent_local_name_py);
                        if (!parent_local_name_c)
                        {
                            PyErr_SetString(PyExc_SystemError, "Failed to convert parent local name to UTF8");
                            goto error_cleanup;
                        }

                        py_text_obj = apply_value_postprocessor_c(parent_local_name_c, trimmed_value_xml);
                        if (!py_text_obj)
                            goto error_cleanup;
                        xmlFree(trimmed_value_xml);
                        trimmed_value_xml = NULL;

                        if (PyDict_Check(current_parent_container_py))
                        {
                            text_key_py = PyUnicode_FromString("#text");
                            if (!text_key_py)
                                goto error_cleanup;

                            existing_text_py = PyDict_GetItem(current_parent_container_py, text_key_py);
                            if (existing_text_py)
                            {
                                if (PyUnicode_Check(existing_text_py))
                                {
                                    new_text_py = PyUnicode_Concat(existing_text_py, py_text_obj);
                                    if (!new_text_py)
                                    {
                                        Py_DECREF(text_key_py);
                                        goto error_cleanup;
                                    }
                                    if (PyDict_SetItem(current_parent_container_py, text_key_py, new_text_py) < 0)
                                    {
                                        Py_DECREF(new_text_py);
                                        Py_DECREF(text_key_py);
                                        goto error_cleanup;
                                    }
                                    Py_DECREF(new_text_py);
                                    new_text_py = NULL;
                                }
                                else
                                {
                                    PyErr_SetString(PyExc_TypeError, "Existing '#text' is not a string.");
                                    Py_DECREF(text_key_py);
                                    goto error_cleanup;
                                }
                            }
                            else
                            {
                                if (PyDict_SetItem(current_parent_container_py, text_key_py, py_text_obj) < 0)
                                {
                                    Py_DECREF(text_key_py);
                                    goto error_cleanup;
                                }
                            }
                            Py_DECREF(text_key_py);
                            text_key_py = NULL;
                        }
                        else if (PyList_Check(current_parent_container_py))
                        {
                            text_key_py = PyUnicode_FromString("#text");
                            if (!text_key_py)
                                goto error_cleanup;
                            attr_tuple_py = PyTuple_Pack(2, text_key_py, py_text_obj);
                            if (!attr_tuple_py)
                            {
                                Py_DECREF(text_key_py);
                                goto error_cleanup;
                            }
                            if (PyList_Append(current_parent_container_py, attr_tuple_py) < 0)
                            {
                                Py_DECREF(attr_tuple_py);
                                Py_DECREF(text_key_py);
                                goto error_cleanup;
                            }
                            Py_DECREF(attr_tuple_py);
                            attr_tuple_py = NULL;
                            Py_DECREF(text_key_py);
                            text_key_py = NULL;
                        }
                        Py_DECREF(py_text_obj);
                        py_text_obj = NULL;
                    }
                    else if (trimmed_value_xml)
                    {
                        xmlFree(trimmed_value_xml);
                        trimmed_value_xml = NULL;
                    }
                }
            }
        }
        parse_ret = xmlTextReaderRead(reader);
    }

    if (parse_ret < 0)
    {
        if (!PyErr_Occurred())
        {
            const xmlError *last_error = xmlGetLastError();
            PyErr_Format(PyExc_RuntimeError, "XML parsing failed with libxml2 XmlTextReader, error code: %d. Message: %s",
                         parse_ret, last_error ? (const char *)last_error->message : "N/A");
        }
        goto error_cleanup;
    }

    if (!result_root_key_py || !result_root_value_py)
    {
        PyErr_SetString(PyExc_ValueError, "Parsed XML was empty or did not produce a valid root element structure.");
        goto error_cleanup;
    }

    PyObject *final_result_dict_py = PyDict_New();
    if (!final_result_dict_py)
        goto error_cleanup;

    if (PyDict_SetItem(final_result_dict_py, result_root_key_py, result_root_value_py) < 0)
    {
        Py_DECREF(final_result_dict_py);
        goto error_cleanup;
    }

    // Normal cleanup for successful path
    Py_DECREF(result_root_key_py);
    result_root_key_py = NULL;
    Py_DECREF(result_root_value_py);
    result_root_value_py = NULL;
    Py_DECREF(parse_stack_py);
    parse_stack_py = NULL;
    Py_DECREF(attr_cache_py);
    attr_cache_py = NULL;
    if (reader)
    {
        xmlFreeTextReader(reader);
        reader = NULL;
    }

    return final_result_dict_py;

error_cleanup:
    Py_XDECREF(result_root_key_py);
    Py_XDECREF(result_root_value_py);
    Py_XDECREF(parse_stack_py);
    Py_XDECREF(attr_cache_py);
    Py_XDECREF(current_local_name_py);
    Py_XDECREF(current_element_obj_py);
    Py_XDECREF(py_attr_value_processed);
    Py_XDECREF(py_attr_qname_for_cache);
    Py_XDECREF(py_prefixed_key_for_dict);
    Py_XDECREF(stack_frame_py);
    Py_XDECREF(popped_frame_py);
    Py_XDECREF(text_key_py);
    Py_XDECREF(py_text_obj);
    Py_XDECREF(new_text_py);
    Py_XDECREF(attr_tuple_py);
    if (trimmed_value_xml)
        xmlFree(trimmed_value_xml);
    if (reader)
        xmlFreeTextReader(reader);

    return NULL;
}

static PyObject *foo(PyObject *self)
{
    // Example usage of libxml2: check its version.
    // This ensures libxml2 is linked and callable.
    xmlCheckVersion(2); // LIBXML_VERSION can also be used if available and preferred.
    return PyUnicode_FromString("bar with libxml2");
}

static PyMethodDef methods[] = {
    {"foo", (PyCFunction)foo, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "xmltodict.lib",
    NULL,
    -1,
    methods,
    NULL, NULL, NULL, NULL};

PyMODINIT_FUNC PyInit_lib(void)
{
    // Import dependencies
    PyObject *datetime_module = PyImport_ImportModule("datetime");
    PyObject *datetime_class = PyObject_GetAttrString(datetime_module, "datetime");
    fromisoformat_func = PyObject_GetAttrString(datetime_class, "fromisoformat");

    PyObject *date_utils_module = PyImport_ImportModule("app.lib.date_utils");
    parse_date_func = PyObject_GetAttrString(date_utils_module, "parse_date");

    return PyModule_Create(&module);
}
