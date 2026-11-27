"""Run focused regressions against code extracted from the published Markdown."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
RULES = Path(os.environ.get('SKILLS_DEV_RULES', REPO / 'skills/rust-skills/rules'))
SCRATCH = Path('/tmp/skills-dev')
SCRATCH.mkdir(mode=0o700, exist_ok=True)
if SCRATCH.is_symlink() or SCRATCH.stat().st_uid != os.getuid():
    raise RuntimeError('Scratch directory must be owned and not a symlink')


def block(name, marker, section=None):
    text = (RULES / (name + '.md')).read_text()
    if section:
        text = text.split(section, 1)[1].split('\n## ', 1)[0]
    return next(s for s in re.findall(r'```rust[^\n]*\n(.*?)\n```', text, re.S) if marker in s)


def function(code, name):
    start = code.index('fn ' + name + '(')
    if code[max(0, start - 7):start] == 'unsafe ':
        start -= 7
    opening = code.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (code[end] == '{') - (code[end] == '}')
        end += 1
    return code[start:end]


class MarkdownExamples(unittest.TestCase):
    def compile(self, source, *, run=True, rejected=False, nightly=False):
        with tempfile.TemporaryDirectory(prefix='examples-', dir=SCRATCH) as td:
            src = Path(td) / 'probe.rs'
            out = Path(td) / 'probe'
            src.write_text(source)
            command = ['rustc']
            if nightly:
                command = ['rustup', 'run', os.environ['SKILLS_DEV_NIGHTLY'], 'rustc']
            args = ['--edition=2024', '-C', 'opt-level=1', str(src), '-o', str(out)]
            if not run:
                args += ['--crate-type=lib']
            result = subprocess.run(command + args, capture_output=True, text=True, timeout=60)
            if rejected:
                self.assertNotEqual(result.returncode, 0, 'An unsafe call was admitted from safe code')
                self.assertIn('E0133', result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                if run:
                    result = subprocess.run([str(out)], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_raw_pointer_requires_unsafe_caller(self):
        code = block('unsafe-minimize-scope', 'fn sum_at', '## Good')
        self.compile(code + '\nfn probe() { let _ = sum_at(std::ptr::null(), 1, 0); }', run=False, rejected=True)

    def test_ffi_copy_requires_unsafe_caller(self):
        code = block('unsafe-extern-block', 'fn copy_bytes', '## Good')
        self.compile(code + '\nfn probe() { copy_bytes(std::ptr::null_mut(), std::ptr::null(), 1); }', run=False, rejected=True)

    def test_fallible_division_rejects_both_exceptional_inputs(self):
        code = function(block('err-result-over-panic', 'fn divide', '## Good'), 'divide')
        self.compile(code + '''
fn main() {
    assert_eq!(divide(10, 2), Ok(5));
    assert!(divide(1, 0).is_err());
    assert!(divide(i32::MIN, -1).is_err());
}
''')

    def test_matrix_rejects_overflow_before_writes(self):
        code = block('opt-bounds-check', 'fn matrix_multiply')
        self.compile(code + '''
fn main() {
    let mut out = [9.0; 4];
    assert!(matrix_multiply(&[], &[], &mut out, usize::MAX).is_err());
    assert_eq!(out, [9.0; 4]);
    assert!(matrix_multiply(&[1.0], &[1.0], &mut out, 2).is_err());
    assert_eq!(out, [9.0; 4]);
    assert!(matrix_multiply(&[], &[], &mut [], 0).is_ok());
    matrix_multiply(&[1.0, 0.0, 0.0, 1.0], &[2.0, 3.0, 4.0, 5.0], &mut out, 2).unwrap();
    assert_eq!(out, [2.0, 3.0, 4.0, 5.0]);
}
''')

    def test_commit_precedes_unlock(self):
        code = block('mem-drop-order', 'fn process', '## Controlling Drop Order for Locals')
        code = '\n'.join(line for line in code.splitlines() if not line.startswith('# '))
        self.compile(code + '''
thread_local! { static EVENTS: std::cell::RefCell<Vec<&'static str>> = const { std::cell::RefCell::new(Vec::new()) }; }
fn record(s: &'static str) { EVENTS.with(|v| v.borrow_mut().push(s)); }
struct Guard;
impl Drop for Guard { fn drop(&mut self) { record("unlock"); } }
struct Transaction;
impl Transaction { fn commit(self) { record("commit"); } }
fn open_connection() {}
fn begin_transaction() -> Transaction { record("begin"); Transaction }
fn acquire_lock() -> Guard { record("lock"); Guard }
fn do_work(_: &Transaction) { record("work"); }
fn main() { process(); EVENTS.with(|v| assert_eq!(*v.borrow(), ["lock", "begin", "work", "commit", "unlock"])); }
''')

    def test_exported_macro_compiles_at_crate_root(self):
        code = block('macro-export-crate-path', 'macro_rules! greet', '## Good')
        self.compile(code, run=False)

    @unittest.skipUnless(os.environ.get('SKILLS_DEV_NIGHTLY'), 'Set SKILLS_DEV_NIGHTLY to test the optional nightly SIMD example')
    def test_simd_offset_slices_and_tails(self):
        code = function(block('opt-simd-portable', 'fn dot_product'), 'dot_product')
        self.compile('''#![feature(portable_simd)]
use std::simd::{f32x8, num::SimdFloat};
''' + code + '''
fn main() {
    let a: Vec<f32> = (0..80).map(|x| x as f32).collect();
    let b: Vec<f32> = (0..80).map(|x| (x + 2) as f32).collect();
    for oa in 0..8 { for ob in 0..8 { for n in 0..40 {
        let x = &a[oa..oa+n]; let y = &b[ob..ob+n];
        let expected: f32 = x.iter().zip(y).map(|(a,b)| a*b).sum();
        assert_eq!(dot_product(x, y), expected, "offsets {oa}/{ob}, length {n}");
    } } }
}
''', nightly=True)


if __name__ == '__main__':
    unittest.main()
