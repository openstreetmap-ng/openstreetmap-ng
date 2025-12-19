use std::cell::UnsafeCell;
use std::hint::unlikely;

use getrandom::getrandom;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

const RAND_BUFFER_SIZE: usize = 8 * 1024; // 8 KiB
const STORAGE_KEY_RAND_SIZE: usize = 16;

thread_local! {
    static RAND_BUFFER: UnsafeCell<BufferedRand> = const { UnsafeCell::new(BufferedRand::new()) };
}

struct BufferedRand {
    buf: [u8; RAND_BUFFER_SIZE],
    pos: usize,
}

impl BufferedRand {
    const fn new() -> Self {
        Self {
            buf: [0; RAND_BUFFER_SIZE],
            pos: RAND_BUFFER_SIZE,
        }
    }

    fn ensure(&mut self, needed: usize) -> PyResult<()> {
        if unlikely(needed > RAND_BUFFER_SIZE) {
            return Err(PyValueError::new_err(format!(
                "Requested {needed} bytes, but buffer is only {RAND_BUFFER_SIZE} bytes"
            )));
        }
        if self.pos + needed > RAND_BUFFER_SIZE {
            getrandom(&mut self.buf).map_err(|e| PyValueError::new_err(e.to_string()))?;
            self.pos = 0;
        }
        Ok(())
    }

    fn take(&mut self, needed: usize) -> PyResult<&[u8]> {
        self.ensure(needed)?;
        let start = self.pos;
        self.pos += needed;
        Ok(&self.buf[start..start + needed])
    }
}

fn with_rand_buffer<R>(f: impl FnOnce(&mut BufferedRand) -> PyResult<R>) -> PyResult<R> {
    RAND_BUFFER.with(|cell| {
        // Safety: `RAND_BUFFER` is thread-local, so this `UnsafeCell` is only accessed from the
        // current thread, and we don't leak references outside this closure.
        let buf = unsafe { &mut *cell.get() };
        f(buf)
    })
}

fn encode_base64url(src: &[u8], suffix: Option<&str>) -> String {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

    let suffix_len = suffix.map_or(0, str::len);
    let mut out = Vec::with_capacity((src.len() * 4).div_ceil(3) + suffix_len);
    let mut i = 0;

    while i + 2 < src.len() {
        let val = ((src[i] as u32) << 16) | ((src[i + 1] as u32) << 8) | (src[i + 2] as u32);
        out.push(ALPHABET[((val >> 18) & 0x3f) as usize]);
        out.push(ALPHABET[((val >> 12) & 0x3f) as usize]);
        out.push(ALPHABET[((val >> 6) & 0x3f) as usize]);
        out.push(ALPHABET[(val & 0x3f) as usize]);
        i += 3;
    }

    match src.len() - i {
        1 => {
            let val = (src[i] as u32) << 16;
            out.push(ALPHABET[((val >> 18) & 0x3f) as usize]);
            out.push(ALPHABET[((val >> 12) & 0x3f) as usize]);
        }
        2 => {
            let val = ((src[i] as u32) << 16) | ((src[i + 1] as u32) << 8);
            out.push(ALPHABET[((val >> 18) & 0x3f) as usize]);
            out.push(ALPHABET[((val >> 12) & 0x3f) as usize]);
            out.push(ALPHABET[((val >> 6) & 0x3f) as usize]);
        }
        _ => {}
    }

    if let Some(suffix) = suffix {
        out.extend_from_slice(suffix.as_bytes());
    }

    // Safety: base64url output is ASCII, and suffix is valid UTF-8.
    unsafe { String::from_utf8_unchecked(out) }
}

#[pyfunction]
fn buffered_randbytes(py: Python<'_>, n: usize) -> PyResult<Py<PyBytes>> {
    with_rand_buffer(|buf| buf.take(n).map(|bytes| PyBytes::new(py, bytes).unbind()))
}

#[pyfunction]
fn buffered_rand_urlsafe(n: usize) -> PyResult<String> {
    with_rand_buffer(|buf| buf.take(n).map(|bytes| encode_base64url(bytes, None)))
}

#[pyfunction(signature = (suffix = ""))]
fn buffered_rand_storage_key(suffix: &str) -> PyResult<String> {
    with_rand_buffer(|buf| {
        buf.take(STORAGE_KEY_RAND_SIZE)
            .map(|bytes| encode_base64url(bytes, Some(suffix)))
    })
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(buffered_randbytes, m)?)?;
    m.add_function(wrap_pyfunction!(buffered_rand_urlsafe, m)?)?;
    m.add_function(wrap_pyfunction!(buffered_rand_storage_key, m)?)?;
    Ok(())
}
