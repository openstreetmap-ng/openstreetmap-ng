use std::borrow::Cow;
use std::hint::{likely, unlikely};

use memchr::{memchr, memchr3};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyAny, PyBool, PyBoolMethods, PyBytes, PyDateAccess, PyDateTime, PyDict, PyList, PyString,
    PyTimeAccess, PyTuple, PyTzInfo, PyTzInfoAccess,
};

static UTC_TZ: PyOnceLock<Py<PyTzInfo>> = PyOnceLock::new();

fn escape_xml<const ESCAPE_QUOTE: bool>(s: &str) -> Cow<'_, str> {
    let bytes = s.as_bytes();
    let needs_escape = memchr3(b'&', b'<', b'>', bytes).is_some()
        || (ESCAPE_QUOTE && memchr(b'"', bytes).is_some());

    if likely(!needs_escape) {
        return Cow::Borrowed(s);
    }

    let mut out = String::with_capacity(s.len() + 10);
    let mut last = 0;

    for (i, &b) in bytes.iter().enumerate() {
        let replacement = match b {
            b'&' => "&amp;",
            b'<' => "&lt;",
            b'>' => "&gt;",
            b'"' if ESCAPE_QUOTE => "&quot;",
            _ => continue,
        };
        out.push_str(&s[last..i]);
        out.push_str(replacement);
        last = i + 1;
    }

    out.push_str(&s[last..]);
    Cow::Owned(out)
}

fn escape_text(s: &str) -> Cow<'_, str> {
    escape_xml::<false>(s)
}

fn escape_attr(s: &str) -> Cow<'_, str> {
    escape_xml::<true>(s)
}

#[allow(clippy::upper_case_acronyms)]
#[allow(non_camel_case_types)]
#[pyclass(frozen)]
pub(crate) struct CDATA {
    text: Py<PyString>,
}

#[pymethods]
impl CDATA {
    #[new]
    fn new(text: Py<PyString>) -> Self {
        Self { text }
    }

    fn __str__(&self, py: Python<'_>) -> Py<PyString> {
        self.text.clone_ref(py)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let repr = self.text.bind(py).repr()?.to_str()?.to_owned();
        Ok(format!("CDATA({repr})"))
    }
}

fn cdata_text(value: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    if let Ok(cdata) = value.extract::<PyRef<CDATA>>() {
        return Ok(Some(cdata.text.bind(value.py()).to_str()?.to_owned()));
    }
    Ok(None)
}

fn to_string<'py>(py: Python<'py>, value: &'py Bound<'py, PyAny>) -> PyResult<Cow<'py, str>> {
    if let Ok(b) = value.cast::<PyBool>() {
        return Ok(Cow::Borrowed(if b.is_true() { "true" } else { "false" }));
    }
    if value.is_none() {
        return Ok(Cow::Borrowed(""));
    }
    if let Ok(s) = value.cast::<PyString>() {
        return Ok(Cow::Borrowed(s.to_str()?));
    }
    if let Ok(dt) = value.cast::<PyDateTime>() {
        if let Some(tzinfo) = dt.get_tzinfo() {
            let tzinfo = tzinfo.unbind();
            let utc = UTC_TZ
                .get_or_try_init(py, || PyTzInfo::utc(py).map(|utc| utc.to_owned().unbind()))?;
            if unlikely(!tzinfo.is(utc)) {
                // Reject non-UTC timestamps to avoid implicit timezone conversion.
                return Err(PyValueError::new_err(format!(
                    "Timezone must be UTC, got {}",
                    tzinfo.bind(py).repr()?.to_str()?
                )));
            }
        }

        let year = dt.get_year();
        let month = dt.get_month();
        let day = dt.get_day();
        let hour = dt.get_hour();
        let minute = dt.get_minute();
        let second = dt.get_second();
        let micro = dt.get_microsecond();
        if micro != 0 {
            return Ok(Cow::Owned(format!(
                "{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{micro:06}Z"
            )));
        }
        return Ok(Cow::Owned(format!(
            "{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z"
        )));
    }

    Ok(Cow::Owned(value.str()?.to_str()?.to_owned()))
}

fn scalar_text<'py>(
    py: Python<'py>,
    value: &'py Bound<'py, PyAny>,
) -> PyResult<(bool, Cow<'py, str>)> {
    if let Some(text) = cdata_text(value)? {
        return Ok((true, Cow::Owned(text)));
    }
    Ok((false, to_string(py, value)?))
}

fn serialize_scalar_element(
    py: Python<'_>,
    key: &str,
    value: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (is_cdata, text) = scalar_text(py, value)?;
    if is_cdata {
        return Ok(format!("<{key}><![CDATA[{text}]]></{key}>"));
    }
    if text.is_empty() {
        return Ok(format!("<{key}/>"));
    }
    let escaped = escape_text(text.as_ref());
    Ok(format!("<{key}>{}</{key}>", escaped))
}

fn serialize_dict_element(py: Python<'_>, key: &str, dict: &Bound<'_, PyDict>) -> PyResult<String> {
    let pairs = dict.iter().map(|(k, v)| {
        let key_s = k
            .cast_into::<PyString>()
            .map_err(|_| PyTypeError::new_err("Dictionary keys must be strings"))?;
        Ok((key_s, v))
    });
    serialize_pairs_element(py, key, dict.len(), pairs)
}

fn serialize_pairs_element<'py, I>(
    py: Python<'py>,
    key: &str,
    len: usize,
    pairs: I,
) -> PyResult<String>
where
    I: IntoIterator<Item = PyResult<(Bound<'py, PyString>, Bound<'py, PyAny>)>>,
{
    let mut attrs_s = String::with_capacity(len * 8);
    let mut inner = String::with_capacity(len * 16);

    for pair in pairs {
        let (k, v) = pair?;
        let key_s = k.to_str()?;
        if let Some(attr_name) = key_s.strip_prefix('@') {
            // Keys prefixed with '@' become XML attributes on the current element.
            attrs_s.push(' ');
            attrs_s.push_str(attr_name);
            attrs_s.push_str("=\"");
            let value_s = to_string(py, &v)?;
            let escaped = escape_attr(value_s.as_ref());
            attrs_s.push_str(escaped.as_ref());
            attrs_s.push('"');
            continue;
        }
        if key_s == "#text" {
            // "#text" writes character data directly inside the element.
            let (is_cdata, text) = scalar_text(py, &v)?;
            if is_cdata {
                inner.push_str("<![CDATA[");
                inner.push_str(text.as_ref());
                inner.push_str("]]>");
            } else {
                let escaped = escape_text(text.as_ref());
                inner.push_str(escaped.as_ref());
            }
            continue;
        }
        inner.push_str(&serialize_element(py, key_s, &v, false)?);
    }

    if inner.is_empty() {
        return Ok(format!("<{key}{attrs_s}/>"));
    }
    Ok(format!("<{key}{attrs_s}>{inner}</{key}>"))
}

fn pair_from_sequence_item(item: &Bound<'_, PyAny>) -> PyResult<Option<(Py<PyString>, Py<PyAny>)>> {
    let pair = if let Ok(t) = item.cast::<PyTuple>() {
        if t.len() == 2 {
            Some((t.get_item(0)?, t.get_item(1)?))
        } else {
            None
        }
    } else if let Ok(l) = item.cast::<PyList>() {
        if l.len() == 2 {
            Some((l.get_item(0)?, l.get_item(1)?))
        } else {
            None
        }
    } else {
        None
    };

    let Some((k, v)) = pair else {
        return Ok(None);
    };

    let k = k
        .cast_into::<PyString>()
        .map_err(|_| PyValueError::new_err("Sequence tuples keys must be strings"))?
        .unbind();
    Ok(Some((k, v.unbind())))
}

fn serialize_sequence(
    py: Python<'_>,
    key: &str,
    seq: &Bound<'_, PyAny>,
    is_root: bool,
) -> PyResult<String> {
    if let Ok(list) = seq.cast::<PyList>() {
        return serialize_sequence_items(py, key, is_root, list.len(), |i| list.get_item(i));
    }
    if let Ok(tuple) = seq.cast::<PyTuple>() {
        return serialize_sequence_items(py, key, is_root, tuple.len(), |i| tuple.get_item(i));
    }
    Err(PyTypeError::new_err("Expected a list or tuple"))
}

fn serialize_sequence_items<'py, F>(
    py: Python<'py>,
    key: &str,
    is_root: bool,
    len: usize,
    mut get_item: F,
) -> PyResult<String>
where
    F: FnMut(usize) -> PyResult<Bound<'py, PyAny>>,
{
    if len == 0 {
        return Ok(String::new());
    }

    // Find all (k, v) pair entries and aggregate them into a single element,
    // placed where the first tuple entry appears (matches the legacy behavior).
    let mut pair_mask = vec![false; len];
    let mut pairs = Vec::with_capacity(len);
    let mut first_pair_index = None;

    for (i, is_pair) in pair_mask.iter_mut().enumerate() {
        let item = get_item(i)?;
        if let Some((k, v)) = pair_from_sequence_item(&item)? {
            if first_pair_index.is_none() {
                first_pair_index = Some(i);
            }
            *is_pair = true;
            pairs.push((k, v));
        }
    }

    let mut out = String::new();

    for (i, is_pair) in pair_mask.iter().enumerate() {
        if Some(i) == first_pair_index {
            // Emit the aggregated pairs where the first pair originally appeared.
            let pairs = std::mem::take(&mut pairs);
            let len = pairs.len();
            let iter = pairs
                .into_iter()
                .map(|(k, v)| Ok((k.into_bound(py), v.into_bound(py))));
            out.push_str(&serialize_pairs_element(py, key, len, iter)?);
            continue;
        }
        if *is_pair {
            continue;
        }

        let bound = get_item(i)?;
        if let Ok(dict) = bound.cast::<PyDict>() {
            if unlikely(is_root && len > 1) {
                return Err(PyValueError::new_err(
                    "Root element cannot contain multiple dicts",
                ));
            }
            out.push_str(&serialize_dict_element(py, key, dict)?);
        } else if bound.cast::<PyList>().is_ok() || bound.cast::<PyTuple>().is_ok() {
            return Err(PyValueError::new_err(
                "Sequence tuples must be (key, value) pairs",
            ));
        } else {
            if unlikely(is_root && len > 1) {
                return Err(PyValueError::new_err(
                    "Root element cannot contain multiple scalars",
                ));
            }
            out.push_str(&serialize_scalar_element(py, key, &bound)?);
        }
    }

    Ok(out)
}

fn serialize_element(
    py: Python<'_>,
    key: &str,
    value: &Bound<'_, PyAny>,
    is_root: bool,
) -> PyResult<String> {
    if let Ok(dict) = value.cast::<PyDict>() {
        return serialize_dict_element(py, key, dict);
    }
    if value.cast::<PyList>().is_ok() || value.cast::<PyTuple>().is_ok() {
        return serialize_sequence(py, key, value, is_root);
    }
    serialize_scalar_element(py, key, value)
}

#[pyfunction]
fn xml_unparse(py: Python<'_>, root: &Bound<'_, PyDict>, binary: bool) -> PyResult<Py<PyAny>> {
    if unlikely(root.len() != 1) {
        return Err(PyValueError::new_err("Invalid root element count"));
    }

    let (key, value) = root.iter().next().unwrap();
    let key = key
        .cast::<PyString>()
        .map_err(|_| PyTypeError::new_err("Root key must be a string"))?;
    let key_s = key.to_str()?;

    let xml = serialize_element(py, key_s, &value, true)?;

    const XML_DECL: &str = "<?xml version='1.0' encoding='UTF-8'?>\n";
    let mut out = String::with_capacity(XML_DECL.len() + xml.len() + 1);
    out.push_str(XML_DECL);
    out.push_str(&xml);
    if !xml.is_empty() {
        out.push('\n');
    }

    if binary {
        Ok(PyBytes::new(py, out.as_bytes()).into_any().unbind())
    } else {
        Ok(PyString::new(py, &out).into_any().unbind())
    }
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CDATA>()?;
    m.add_function(wrap_pyfunction!(xml_unparse, m)?)?;
    Ok(())
}
