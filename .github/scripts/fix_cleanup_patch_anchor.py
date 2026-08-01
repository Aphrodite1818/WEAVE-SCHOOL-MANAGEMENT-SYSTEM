from pathlib import Path

path = Path(".github/scripts/apply_frontend_guide_and_import_cleanup.py")
content = path.read_text(encoding="utf-8")
old = '''replace_once(
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
new = '''replace_once(
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
if old not in content:
    raise RuntimeError("stale admin setup status anchor was not found")
path.write_text(content.replace(old, new, 1), encoding="utf-8")
