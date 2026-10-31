#!/usr/bin/env python3
"""Compile and run Android-independent recovery tests with a local JDK 17+."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
java_home = os.environ.get('JAVA_HOME')
java = str(Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')) if java_home else shutil.which('java')
if not java:
    raise SystemExit('Install JDK 17+ and set JAVA_HOME or add java to PATH.')
sources = root/'alien-google-auth/src/main/java/com/conradmafer/aliencolonies/auth'
with tempfile.TemporaryDirectory(prefix='alien-auth-test-') as temporary:
    subprocess.run([java, '--module', 'jdk.compiler/com.sun.tools.javac.Main', '-d', temporary,
                    str(sources/'NativeSignInMailbox.java'), str(sources/'AuthReturnMailbox.java'),
                    str(root/'recovery_evidence/RecoveredMailboxTest.java')], check=True)
    subprocess.run([java, '-cp', temporary, 'com.conradmafer.aliencolonies.auth.RecoveredMailboxTest'], check=True)
