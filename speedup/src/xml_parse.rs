use ahash::AHashMap;
use std::borrow::Cow;
use std::fmt::Display;
use std::hint::unlikely;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyBytes, PyDict, PyList, PyString, PyTuple};
use quick_xml::Reader;
use quick_xml::escape::unescape as xml_unescape;
use quick_xml::events::Event;
use quick_xml::events::attributes::Attribute;

const STACK_SIZE: usize = 10;

type StackFrame = (
    Py<PyString>,
    Option<Py<PyDict>>,
    Option<Py<PyList>>,
    Option<String>,
);

fn is_force_items(name: &str) -> bool {
    // Elements where sibling order matters and duplicates are expected (e.g. osmChange create/modify/delete).
    matches!(
        name,
        "bounds" | "create" | "delete" | "modify" | "node" | "relation" | "way"
    )
}

fn is_force_list(name: &str) -> bool {
    // Elements which are always represented as lists in the Python shape, even with a single entry.
    matches!(
        name,
        "comment"
            | "gpx_file"
            | "member"
            | "nd"
            | "note"
            | "preference"
            | "tag"
            | "trk"
            | "trkpt"
            | "trkseg"
    )
}

struct ParseState {
    stack: Vec<StackFrame>,
    current_name: Option<Py<PyString>>,
    current_dict: Option<Py<PyDict>>,
    current_list: Option<Py<PyList>>,
    current_text: Option<String>,
    result: Option<Py<PyDict>>,
    tag_cache: AHashMap<Vec<u8>, Py<PyString>>,
    attr_cache: AHashMap<Vec<u8>, Py<PyString>>,
    text_key: Py<PyString>,
}

impl ParseState {
    fn new(py: Python<'_>) -> Self {
        Self {
            stack: Vec::with_capacity(STACK_SIZE),
            current_name: None,
            current_dict: None,
            current_list: None,
            current_text: None,
            result: None,
            tag_cache: AHashMap::with_capacity(32),
            attr_cache: AHashMap::with_capacity(64),
            text_key: PyString::new(py, "#text").unbind(),
        }
    }

    fn add_attributes<'a, I, E>(
        &mut self,
        py: Python<'_>,
        attrs: I,
        datetime_fromisoformat: &Bound<'_, PyAny>,
        parse_date: &Bound<'_, PyAny>,
    ) -> PyResult<()>
    where
        I: Iterator<Item = Result<Attribute<'a>, E>>,
        E: Display,
    {
        for attr in attrs {
            let attr = attr.map_err(|e| PyValueError::new_err(e.to_string()))?;
            let key_raw = attr.key.as_ref();
            let key_s =
                std::str::from_utf8(key_raw).map_err(|e| PyValueError::new_err(e.to_string()))?;
            let value_unescaped = attr
                .unescape_value()
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
            let value_s = value_unescaped.as_ref();

            let value_obj =
                postprocess_value(py, datetime_fromisoformat, parse_date, key_s, value_s)?;

            let dict = self
                .current_dict
                .get_or_insert_with(|| PyDict::new(py).unbind());
            let set_key = cached_attr_key(py, &mut self.attr_cache, key_raw, key_s);
            dict.bind(py).set_item(set_key, value_obj)?;
        }
        Ok(())
    }

    fn start_element<'a, I, E>(
        &mut self,
        py: Python<'_>,
        name_raw: &[u8],
        attrs: I,
        datetime_fromisoformat: &Bound<'_, PyAny>,
        parse_date: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyString>>
    where
        I: Iterator<Item = Result<Attribute<'a>, E>>,
        E: Display,
    {
        if unlikely(self.stack.len() >= STACK_SIZE) {
            return Err(PyValueError::new_err(format!(
                "XML nesting depth exceeded limit of {STACK_SIZE}"
            )));
        }

        if let Some(name) = self.current_name.take() {
            self.stack.push((
                name,
                self.current_dict.take(),
                self.current_list.take(),
                self.current_text.take(),
            ));
        }

        let name_obj = cached_name(py, &mut self.tag_cache, name_raw)?;
        self.current_name = Some(name_obj.clone_ref(py));
        self.current_text = None;

        self.add_attributes(py, attrs, datetime_fromisoformat, parse_date)?;

        Ok(name_obj)
    }

    fn finalize_element(&mut self, py: Python<'_>, end_name: Py<PyString>) -> PyResult<()> {
        let end_name_s = end_name.bind(py).to_str()?;
        let current_result = match (self.current_dict.take(), self.current_list.take()) {
            (None, None) => None,
            (Some(dict), None) => {
                let dict_b = dict.bind(py);
                if dict_b.len() == 1 && dict_b.contains(self.text_key.clone_ref(py))? {
                    // Collapse pure text nodes to a scalar instead of {"#text": value}.
                    Some(
                        dict_b
                            .get_item(self.text_key.clone_ref(py))?
                            .unwrap()
                            .unbind(),
                    )
                } else {
                    Some(dict.into_any())
                }
            }
            (None, Some(list)) => Some(list.into_any()),
            (Some(dict), Some(list)) => {
                let merged = PyList::empty(py);
                for (k, v) in dict.bind(py).iter() {
                    let tuple = PyTuple::new(py, [k.unbind(), v.unbind()])?.unbind();
                    merged.append(tuple)?;
                }
                for item in list.bind(py).iter() {
                    merged.append(item)?;
                }
                Some(merged.unbind().into_any())
            }
        };

        if let Some((parent_name, mut parent_dict, mut parent_list, parent_text)) = self.stack.pop()
        {
            if let Some(child_value) = current_result {
                if let Some(list) = parent_list.as_ref() {
                    // Already in list-of-pairs mode; keep child elements in document order.
                    let tuple = PyTuple::new(py, [end_name.clone_ref(py).into_any(), child_value])?
                        .unbind();
                    list.bind(py).append(tuple)?;
                } else if is_force_items(end_name_s) {
                    // Switch to list-of-pairs to preserve sibling order and allow duplicates.
                    let list = PyList::empty(py).unbind();
                    if let Some(dict) = parent_dict.take() {
                        for (k, v) in dict.bind(py).iter() {
                            let tuple = PyTuple::new(py, [k.unbind(), v.unbind()])?.unbind();
                            list.bind(py).append(tuple)?;
                        }
                    }
                    let tuple = PyTuple::new(py, [end_name.clone_ref(py).into_any(), child_value])?
                        .unbind();
                    list.bind(py).append(tuple)?;
                    parent_list = Some(list);
                } else {
                    let dict = parent_dict.get_or_insert_with(|| PyDict::new(py).unbind());
                    let key_obj = end_name.clone_ref(py);

                    if let Some(existing) = dict.bind(py).get_item(key_obj.bind(py))? {
                        if let Ok(existing_list) = existing.cast::<PyList>() {
                            // Repeated tags become lists to preserve all occurrences.
                            existing_list.append(child_value)?;
                        } else {
                            let new_list = PyList::new(py, [existing.unbind(), child_value])?;
                            dict.bind(py).set_item(key_obj.bind(py), new_list)?;
                        }
                    } else if is_force_list(end_name_s) {
                        // Some tags are always treated as lists even with a single entry.
                        let new_list = PyList::new(py, [child_value])?;
                        dict.bind(py).set_item(key_obj.bind(py), new_list)?;
                    } else {
                        dict.bind(py).set_item(key_obj.bind(py), child_value)?;
                    }
                }
            }

            self.current_name = Some(parent_name);
            self.current_dict = parent_dict;
            self.current_list = parent_list;
            self.current_text = parent_text;
        } else if let Some(child_value) = current_result {
            let out = PyDict::new(py);
            out.set_item(end_name, child_value)?;
            self.result = Some(out.unbind());
        }

        Ok(())
    }

    fn handle_text(
        &mut self,
        py: Python<'_>,
        text: &str,
        datetime_fromisoformat: &Bound<'_, PyAny>,
        parse_date: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        if text.trim().is_empty() {
            return Ok(());
        }
        let Some(name) = self.current_name.as_ref() else {
            return Ok(());
        };

        let key_s = name.bind(py).to_str()?;
        let value_obj = postprocess_value(py, datetime_fromisoformat, parse_date, key_s, text)?;

        if let Some(list) = self.current_list.as_ref() {
            let tuple =
                PyTuple::new(py, [self.text_key.clone_ref(py).into_any(), value_obj])?.unbind();
            list.bind(py).append(tuple)?;
            return Ok(());
        }

        let dict = self
            .current_dict
            .get_or_insert_with(|| PyDict::new(py).unbind());
        let dict_b = dict.bind(py);

        if let Some(accum) = self.current_text.as_mut() {
            let value_bound = value_obj.bind(py);
            let new_s = value_to_string(value_bound)?;
            // The XML parser can split character data across multiple events; concatenate.
            accum.push_str(new_s.as_ref());
            dict_b.set_item(self.text_key.clone_ref(py), PyString::new(py, accum))?;
            return Ok(());
        }

        if let Some(existing) = dict_b.get_item(self.text_key.clone_ref(py))? {
            let value_bound = value_obj.bind(py);
            let existing_s = value_to_string(&existing)?;
            let new_s = value_to_string(value_bound)?;
            // Second text event: seed the accumulation buffer from the existing "#text" value.
            let mut combined = String::with_capacity(existing_s.len() + new_s.len());
            combined.push_str(existing_s.as_ref());
            combined.push_str(new_s.as_ref());
            dict_b.set_item(self.text_key.clone_ref(py), PyString::new(py, &combined))?;
            self.current_text = Some(combined);
        } else {
            dict_b.set_item(self.text_key.clone_ref(py), value_obj)?;
        }

        Ok(())
    }
}

fn value_to_string<'py>(value: &'py Bound<'py, PyAny>) -> PyResult<Cow<'py, str>> {
    if let Ok(s) = value.cast::<PyString>() {
        Ok(Cow::Borrowed(s.to_str()?))
    } else {
        Ok(Cow::Owned(value.str()?.to_str()?.to_owned()))
    }
}

fn cached_name(
    py: Python<'_>,
    cache: &mut AHashMap<Vec<u8>, Py<PyString>>,
    name_raw: &[u8],
) -> PyResult<Py<PyString>> {
    if let Some(cached) = cache.get(name_raw) {
        return Ok(cached.clone_ref(py));
    }
    let s = std::str::from_utf8(name_raw).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let py_s = PyString::new(py, s).unbind();
    cache.insert(name_raw.to_vec(), py_s.clone_ref(py));
    Ok(py_s)
}

fn cached_attr_key(
    py: Python<'_>,
    cache: &mut AHashMap<Vec<u8>, Py<PyString>>,
    key_raw: &[u8],
    key_s: &str,
) -> Py<PyString> {
    if let Some(cached) = cache.get(key_raw) {
        return cached.clone_ref(py);
    }
    let py_key = PyString::new(py, &format!("@{key_s}")).unbind();
    cache.insert(key_raw.to_vec(), py_key.clone_ref(py));
    py_key
}

fn postprocess_value(
    py: Python<'_>,
    datetime_fromisoformat: &Bound<'_, PyAny>,
    parse_date: &Bound<'_, PyAny>,
    key: &str,
    value: &str,
) -> PyResult<Py<PyAny>> {
    let parse_i64 = |value: &str| {
        value
            .parse::<i64>()
            .map(|v| v.into_pyobject(py).unwrap().into_any().unbind())
            .map_err(|e| PyValueError::new_err(e.to_string()))
    };
    let parse_f64 = |value: &str| {
        value
            .parse::<f64>()
            .map(|v| v.into_pyobject(py).unwrap().into_any().unbind())
            .map_err(|e| PyValueError::new_err(e.to_string()))
    };

    match key {
        // Coerce common scalar keys (OSM-ish) for parity with the Python layer; fallback is string.
        "open" | "pending" | "visible" => match value {
            "true" => Ok(PyBool::new(py, true).to_owned().into_any().unbind()),
            "false" => Ok(PyBool::new(py, false).to_owned().into_any().unbind()),
            _ => Err(PyValueError::new_err(format!(
                "{value:?} is neither 'true' nor 'false'"
            ))),
        },
        "ele" | "lat" | "lon" | "max_lat" | "max_lon" | "min_lat" | "min_lon" => parse_f64(value),
        "changes_count" | "changeset" | "comments_count" | "id" | "num_changes" | "ref" | "uid" => {
            parse_i64(value)
        }
        "version" => {
            if value.contains('.') {
                parse_f64(value)
            } else {
                parse_i64(value)
            }
        }
        "closed_at" | "created_at" | "date" | "time" | "timestamp" | "updated_at" => {
            let callable = if value.contains(' ') {
                parse_date
            } else {
                datetime_fromisoformat
            };
            let arg = PyString::new(py, value);
            callable.call1((arg,)).map(|o| o.unbind())
        }
        _ => Ok(PyString::new(py, value).into_any().unbind()),
    }
}

#[pyfunction]
fn xml_parse(py: Python<'_>, xml: &Bound<'_, PyBytes>) -> PyResult<Py<PyAny>> {
    let datetime = py.import("datetime")?.getattr("datetime")?;
    let datetime_fromisoformat = datetime.getattr("fromisoformat")?;
    let parse_date = py.import("app.lib.date_utils")?.getattr("parse_date")?;

    let mut reader = Reader::from_reader(xml.as_bytes());
    let mut state = ParseState::new(py);
    let mut buf = Vec::with_capacity(xml.as_bytes().len().min(1024));

    loop {
        buf.clear();
        let event = reader
            .read_event_into(&mut buf)
            .map_err(|e| PyValueError::new_err(format!("Error parsing XML: {e}")))?;

        match event {
            Event::Start(e) => {
                let local_name = e.local_name();
                let name_raw = local_name.as_ref();
                state.start_element(
                    py,
                    name_raw,
                    e.attributes(),
                    &datetime_fromisoformat,
                    &parse_date,
                )?;
            }
            Event::Empty(e) => {
                let local_name = e.local_name();
                let name_raw = local_name.as_ref();
                let end_name = state.start_element(
                    py,
                    name_raw,
                    e.attributes(),
                    &datetime_fromisoformat,
                    &parse_date,
                )?;
                state.finalize_element(py, end_name)?;
            }
            Event::Text(e) => {
                let decoded = e
                    .decode()
                    .map_err(|e| PyValueError::new_err(e.to_string()))?;
                let unescaped = xml_unescape(decoded.as_ref())
                    .map_err(|e| PyValueError::new_err(e.to_string()))?;
                state.handle_text(py, unescaped.as_ref(), &datetime_fromisoformat, &parse_date)?;
            }
            Event::CData(e) => {
                let decoded = e
                    .decode()
                    .map_err(|e| PyValueError::new_err(e.to_string()))?;
                state.handle_text(py, decoded.as_ref(), &datetime_fromisoformat, &parse_date)?;
            }
            Event::GeneralRef(e) => {
                let decoded = e
                    .decode()
                    .map_err(|e| PyValueError::new_err(e.to_string()))?;

                // `BytesRef` data does not include the leading '&' (reader skips it) and
                // slice reader also strips the trailing ';'. Reconstruct the full reference so
                // we can reuse quick-xml's unescape implementation.
                let mut reference = String::with_capacity(decoded.len() + 2);
                reference.push('&');
                reference.push_str(decoded.as_ref());
                reference.push(';');

                let resolved =
                    xml_unescape(&reference).map_err(|e| PyValueError::new_err(e.to_string()))?;
                state.handle_text(py, resolved.as_ref(), &datetime_fromisoformat, &parse_date)?;
            }
            Event::End(_e) => {
                let Some(end_name) = state.current_name.take() else {
                    continue;
                };
                state.finalize_element(py, end_name)?;
            }
            Event::Eof => break,
            _ => {}
        }
    }

    let out = state
        .result
        .ok_or_else(|| PyValueError::new_err("Document is empty"))?;
    Ok(out.into_any())
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(xml_parse, m)?)?;
    Ok(())
}
