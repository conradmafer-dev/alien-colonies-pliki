#!/usr/bin/env python3
"""Build this resource-free Java Android library using JDK and Android SDK directly.

The normal Android application export still uses Godot/Gradle and the dependencies
in export_plugin.gd. This builds only the plugin AAR, not an APK or AAB.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sdk', default=os.environ.get('ANDROID_HOME'))
parser.add_argument('--jdk', default=os.environ.get('JAVA_HOME'))
parser.add_argument('--dependencies', type=Path, default=ROOT/'.portable-cache')
args = parser.parse_args()
if not args.sdk or not args.jdk:
    parser.error('Set ANDROID_HOME and JAVA_HOME, or pass --sdk and --jdk (JDK 17).')
sdk, jdk = Path(args.sdk).resolve(), Path(args.jdk).resolve()
android_jar = sdk/'platforms/android-36/android.jar'
if not android_jar.is_file():
    parser.error('Android SDK platform android-36/android.jar is required.')
d8_jar = sdk/'build-tools/36.0.0/lib/d8.jar'
if not d8_jar.is_file():
    parser.error('Android SDK build-tools 36.0.0 (lib/d8.jar) is required.')
java = jdk/'bin'/('java.exe' if os.name == 'nt' else 'java')
args.dependencies.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ROOT/'portable_dependencies.json').read_text())
classpath = [android_jar]
for name, entry in manifest.items():
    artifact = args.dependencies/name
    if not artifact.exists():
        print('Downloading', name, flush=True)
        with urllib.request.urlopen(entry['url'], timeout=180) as response, artifact.open('wb') as target:
            shutil.copyfileobj(response, target)
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != entry['sha256']:
        raise SystemExit('Checksum mismatch: '+str(artifact))
    if name.endswith('.aar'):
        extracted = artifact.with_suffix('.jar')
        with zipfile.ZipFile(artifact) as archive:
            extracted.write_bytes(archive.read('classes.jar'))
        classpath.append(extracted)
    else:
        classpath.append(artifact)

def deterministic_zip(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return result.getvalue()

module = ROOT/'alien-google-auth'
ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
android_manifest = ET.parse(module/'src/main/AndroidManifest.xml').getroot()
android_manifest.set('package', 'com.conradmafer.aliencolonies.auth')
uses_sdk = ET.Element('uses-sdk')
uses_sdk.set('{http://schemas.android.com/apk/res/android}minSdkVersion', '23')
android_manifest.insert(0, uses_sdk)
manifest_bytes = ET.tostring(android_manifest, encoding='utf-8', xml_declaration=True)
sources = sorted((module/'src/main/java').rglob('*.java'))
report = {'method': 'javac 17 against official SDK/dependencies; deterministic resource-free AAR packaging',
          'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
          'dependency_sha256': {n: e['sha256'] for n,e in manifest.items()}, 'variants': {}}
with tempfile.TemporaryDirectory(prefix='alien-google-auth-') as temporary:
    for variant in ['debug', 'release']:
        classes = Path(temporary)/variant
        classes.mkdir()
        command = [str(java), '--module', 'jdk.compiler/com.sun.tools.javac.Main',
                   '-encoding', 'UTF-8', '--release', '17', '-g' if variant == 'debug' else '-g:none',
                   '-cp', os.pathsep.join(map(str,classpath)), '-d', str(classes)]
        subprocess.run(command+list(map(str,sources)), check=True)
        entries = {str(p.relative_to(classes)).replace(os.sep,'/'): p.read_bytes() for p in classes.rglob('*.class')}
        jar = deterministic_zip(entries)
        class_jar = Path(temporary)/(variant+'-classes.jar')
        class_jar.write_bytes(jar)
        dex_output = Path(temporary)/(variant+'-dex.zip')
        d8 = [str(java), '-cp', str(d8_jar), 'com.android.tools.r8.D8', '--'+variant,
              '--min-api', '23', '--lib', str(android_jar)]
        for dependency in classpath[1:]:
            d8.extend(['--classpath', str(dependency)])
        subprocess.run(d8+['--output',str(dex_output),str(class_jar)], check=True)
        aar = deterministic_zip({'AndroidManifest.xml': manifest_bytes, 'classes.jar': jar,
                                 'proguard.txt': (module/'consumer-rules.pro').read_bytes(), 'R.txt': b'',
                                 'META-INF/com/android/build/gradle/aar-metadata.properties':
                                 b'aarFormatVersion=1.0\naarMetadataVersion=1.0\nminCompileSdk=23\nminCompileSdkExtension=0\n'})
        output = ROOT.parent.parent/'addons/AlienGoogleAuth/bin'/variant/('AlienGoogleAuth-'+variant+'.aar')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(aar)
        report['variants'][variant] = {'file':str(output.relative_to(ROOT.parent.parent)),
                                       'sha256':hashlib.sha256(aar).hexdigest(), 'class_count':len(entries),
                                       'javac':'pass', 'd8':'pass',
                                       'verification_dex_sha256':hashlib.sha256(dex_output.read_bytes()).hexdigest()}
        print('Built', output)
(ROOT/'BUILD_VERIFICATION.json').write_text(json.dumps(report, indent=2)+'\n')
