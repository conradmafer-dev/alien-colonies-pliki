#!/usr/bin/env python3
"""Apply the verified API36 and launcher configuration after installing Godot4.5.1 templates."""
from pathlib import Path
import re
import shutil


def configure(project: Path) -> None:
    build = project / 'android' / 'build'
    config = build / 'config.gradle'
    build_config = build / 'build.gradle'
    launcher_hook = Path(__file__).with_name('preserve_launcher88.gradle')
    if not config.is_file() or not build_config.is_file():
        raise SystemExit('First install the Android build template from Godot 4.5.1, then run this script again.')
    if not launcher_hook.is_file():
        raise SystemExit('Missing tools/preserve_launcher88.gradle. Extract the complete source package before configuring Android.')
    text = config.read_text(encoding='utf-8')
    values = {'androidGradlePlugin': "'8.10.1'", 'compileSdk': '36', 'targetSdk': '36', 'buildTools': "'36.0.0'"}
    for name, value in values.items():
        pattern = rf'^(\s*{name}\s*:\s*)[^,]+(,)'
        text, count = re.subn(pattern, lambda match: match.group(1) + value + match.group(2), text, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f'Expected one {name} setting in Godot 4.5.1 config.gradle; found {count}. No file changed.')
    build_text = build_config.read_text(encoding='utf-8')
    hook_pattern = r"^\s*apply\s+from:\s*['\"]preserve_launcher88\.gradle['\"]\s*$"
    hook_count = len(re.findall(hook_pattern, build_text, re.MULTILINE))
    if hook_count > 1:
        raise SystemExit('Duplicate launcher hook declarations in build.gradle. No file changed.')
    if hook_count == 0:
        build_text = build_text.rstrip() + "\n\napply from: 'preserve_launcher88.gradle'\n"
    config.write_text(text, encoding='utf-8')
    build_config.write_text(build_text, encoding='utf-8')
    shutil.copyfile(launcher_hook, build / launcher_hook.name)
    cleanup_hook = Path(__file__).with_name('clean_asset_pack_temp93.gradle')
    if cleanup_hook.is_file():
        shutil.copyfile(cleanup_hook, build / cleanup_hook.name)
        line = "apply from: 'clean_asset_pack_temp93.gradle'"
        if line not in build_text:
            build_text = build_config.read_text(encoding='utf-8').rstrip() + '\n' + line + '\n'
            build_config.write_text(build_text, encoding='utf-8')
    wrapper = build / 'gradlew'
    if wrapper.is_file():
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
    print('Android build: AGP8.10.1, compile/target SDK36, build-tools36.0.0; active adaptive launcher icon includes the monochrome layer. Gradle8.11.1 and Java17 remain as in the original template.')


if __name__ == '__main__':
    configure(Path(__file__).resolve().parents[1])
