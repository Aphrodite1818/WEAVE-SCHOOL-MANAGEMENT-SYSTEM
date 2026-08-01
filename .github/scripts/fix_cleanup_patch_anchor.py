from pathlib import Path

path = Path(".github/scripts/apply_frontend_guide_and_import_cleanup.py")
content = path.read_text(encoding="utf-8")

old_admin = '''replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    ''' + "'''" + '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${classes.length} classes · ${subjects.length} subjects`}
                />
                <SetupCheck
                  label="Academic period active"
''' + "'''" + ''',
    ''' + "'''" + '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${activeClasses.length} classes · ${activeSubjects.length} subjects`}
                />
                <SetupCheck
                  label="Class progression"
                  complete={completionMap.progression}
                  detail={progressionComplete ? "Every active class has a destination" : "Choose next classes or terminal classes"}
                />
                <SetupCheck
                  label="Academic period active"
''' + "'''" + ''',
)
'''
new_admin = '''replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    ''' + "'''" + '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${classes.length} classes · ${subjects.length} subjects`}
                />
                <SetupCheck
                  label="Session open"
''' + "'''" + ''',
    ''' + "'''" + '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${activeClasses.length} classes · ${activeSubjects.length} subjects`}
                />
                <SetupCheck
                  label="Class progression"
                  complete={completionMap.progression}
                  detail={progressionComplete ? "Every active class has a destination" : "Choose next classes or terminal classes"}
                />
                <SetupCheck
                  label="Session open"
''' + "'''" + ''',
)
'''
if old_admin not in content:
    raise RuntimeError("stale admin setup status anchor was not found")
content = content.replace(old_admin, new_admin, 1)

old_confirmation = '''replace_once(
    "backend/app/modules/bulk_imports/service.py",
    ''' + "'''" + '''                skipped_rows=0,
            ),
        )

        validation_results = [
''' + "'''" + ''',
    ''' + "'''" + '''                skipped_rows=0,
                source_fingerprint=source_fingerprint,
                confirmed_fingerprint=source_fingerprint,
            ),
        )

        validation_results = [
''' + "'''" + ''',
)
'''
new_confirmation = '''replace_once(
    "backend/app/modules/bulk_imports/service.py",
    ''' + "'''" + '''                successful_rows=0,
                failed_rows=0,
                processed_rows=0,
            ),
        )

        validation_results = [
''' + "'''" + ''',
    ''' + "'''" + '''                successful_rows=0,
                failed_rows=0,
                processed_rows=0,
                source_fingerprint=source_fingerprint,
                confirmed_fingerprint=source_fingerprint,
            ),
        )

        validation_results = [
''' + "'''" + ''',
)
'''
if old_confirmation not in content:
    raise RuntimeError("stale import confirmation anchor was not found")
content = content.replace(old_confirmation, new_confirmation, 1)

path.write_text(content, encoding="utf-8")
