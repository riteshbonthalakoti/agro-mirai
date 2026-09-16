import io

path = r"C:\Projects\AGRO MIRAI\mobile\App.tsx"
with io.open(path, encoding="utf-8") as f:
    lines = f.readlines()

# Find each occurrence of a line starting with settingsReportBugRow and
# remove that line plus the following 14 lines that belong to my bad
# duplicate insert (bugReportTitle through bugReportError), which all
# sit directly below a settingsLanguageRow line and above the next real
# key (settingsNoFieldYet / homeNoFieldTitle / etc, or the te: block
# opener).
out = []
i = 0
removed_blocks = 0
while i < len(lines):
    line = lines[i]
    if line.strip().startswith("settingsReportBugRow:"):
        # remove this line and all consecutive lines that are part of the
        # bad block (bugReport* keys I introduced), stopping at the first
        # line that is NOT one of those keys.
        bad_prefixes = (
            "settingsReportBugRow:", "bugReportTitle:", "bugReportSubtitle:",
            "bugReportReasonCrash:", "bugReportReasonWrongInfo:", "bugReportReasonUnclear:",
            "bugReportReasonOther:", "bugReportMessagePlaceholder:", "bugReportAttachPhoto:",
            "bugReportPhotoNote:", "bugReportSubmit:", "bugReportSubmitting:",
            "bugReportValidation:", "bugReportSuccess:", "bugReportError:",
        )
        j = i
        while j < len(lines) and lines[j].strip().startswith(bad_prefixes):
            j += 1
        removed_blocks += 1
        i = j
        continue
    out.append(line)
    i += 1

with io.open(path, "w", encoding="utf-8") as f:
    f.writelines(out)
print("removed blocks:", removed_blocks)
