"""Optional Cargo tests for actual arena/channel snippets; no source workspace build."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_examples import block, REPO, SCRATCH


@unittest.skipUnless(os.environ.get('SKILLS_DEV_RUNTIME'), 'Set SKILLS_DEV_RUNTIME=1 for Cargo-backed examples')
class RuntimeExamples(unittest.TestCase):
    def test_arena_eof_and_broadcast_recovery(self):
        arena = block('mem-arena-allocator', 'fn with_scratch')
        cancel = block('async-cancel-safety', 'async fn good_example', '## Good')
        broadcast = block('async-broadcast-pubsub', 'async fn receive_events', '## Good')
        source = 'mod arena {\n' + arena + '''
#[test]
fn repeated_scratch_calls_and_reentrancy() {
    assert_eq!(with_scratch(|a| *a.alloc(42)).unwrap(), 42);
    assert_eq!(with_scratch(|a| *a.alloc(43)).unwrap(), 43);
    let nested = with_scratch(|_| with_scratch(|_| 0)).unwrap();
    assert!(nested.is_err());
    assert!(with_scratch(|_| ()).is_ok());
}
} mod cancellation {
''' + cancel + '''
#[tokio::test]
async fn eof_and_closed_control_channel() {
    let (tx, mut rx) = mpsc::channel(1);
    drop(tx);
    let data = [7_u8; 2048];
    let result = tokio::time::timeout(std::time::Duration::from_secs(1), good_example(&mut &data[..], &mut rx)).await;
    assert_eq!(result.unwrap().unwrap(), 2);
}
#[tokio::test]
async fn partial_frame_is_rejected() {
    let (_tx, mut rx) = mpsc::channel(1);
    let result = good_example(&mut &b"short"[..], &mut rx).await;
    assert_eq!(result.unwrap_err().kind(), std::io::ErrorKind::UnexpectedEof);
}
} mod broadcast_recovery {
''' + broadcast + '''
#[tokio::test]
async fn lag_does_not_end_subscription() {
    let (tx, mut rx) = broadcast::channel(2);
    tx.send(1).unwrap(); tx.send(2).unwrap(); tx.send(3).unwrap(); drop(tx);
    let mut events = Vec::new(); let mut lag = 0;
    receive_events(&mut rx, |event| events.push(event), |n| lag += n).await;
    assert_eq!(events, vec![2, 3]); assert_eq!(lag, 1);
}
}
'''
        watch = block('async-watch-latest', 'let config = rx.', '## Good')
        accessors = re.findall(r'let config = rx\.(borrow(?:_and_update)?)\(\)', watch)
        self.assertEqual(len(accessors), 2)
        for i, accessor in enumerate(accessors):
            source += f"""
#[tokio::test]
async fn watch_race_{i}() {{
    let (tx, mut rx) = tokio::sync::watch::channel(0);
    tx.send(1).unwrap(); rx.changed().await.unwrap();
    tx.send(2).unwrap(); // Newer update between notification and read.
    let value = *rx.{accessor}();
    assert_eq!(value, 2);
    assert!(!rx.has_changed().unwrap(), "read value must be marked seen");
    drop(tx);
    assert!(rx.changed().await.is_err());
}}
"""
        with tempfile.TemporaryDirectory(prefix='runtime-', dir=SCRATCH) as td:
            root = Path(td)
            (root / 'src').mkdir()
            (root / 'src/lib.rs').write_text(source)
            for name in ['Cargo.toml', 'Cargo.lock']:
                shutil.copyfile(REPO / 'tests/runtime' / name, root / name)
            # Reuse one target for this active validation run when supplied.
            target = os.environ.get('SKILLS_DEV_CARGO_TARGET', str(root / 'target'))
            result = subprocess.run(['cargo', 'test', '--locked', '--offline', '--manifest-path', str(root / 'Cargo.toml')], env={**os.environ, 'CARGO_TARGET_DIR': target}, capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('6 passed', result.stdout)
            print('Cargo-backed examples: six runtime tests passed')

if __name__ == '__main__':
    unittest.main()
