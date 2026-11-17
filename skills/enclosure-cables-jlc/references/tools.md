# Tools: how each is found, how to ask for it, what works without it

Run `python -I <skill folder>/scripts/env_check.py --project <project>/mech` at the start of every session. It
prints one table: tool, found, MISSING or declined, version or place, and the phases that cannot run without it. A
tool the user declined (`[tools] slicer = "none"`, likewise `blender`, `chrome`) is shown as declined, is never looked
for and is never used. It never installs, downloads or opens a network connection. Run it again once `mech.toml`
holds the user's `[tools]` answers.

**Never install without the user's yes** (SKILL.md rule 15). Ask with the question shape, one tool per question:

```
<Tool> is missing. May I install it?
Suggested: yes, <where it goes>.
Why: <what cannot run without it>.
```

A missing tool never turns into a pass: the rows that need it read "could not run" (rule 8), and the gate summary
lists them.

## 1. Summary

| Tool | Needed for | Found by | Without it |
|---|---|---|---|
| Python 3.10 or newer | every script | the interpreter that runs `env_check.py` | nothing runs: ask the user to install Python |
| CadQuery (in its own Python environment) | the model, fit, pair checks, sheet features, drawings, rule measure, views, print audit of STEP files | this interpreter, `CADQUERY_PYTHON`, `[tools] cadquery_python`, a venv beside the project | the model, fit and drawing checks could not run. Reviews of drawings someone else made, the cable scripts (routes without model clearance), the catalogue scan and all order phases still work |
| numpy, shapely, ezdxf, matplotlib, scipy, Pillow, PyMuPDF, vtk | print files, drawings, cable drawings, views, PDF text | import test, each | the script that needs one exits 2 and names it |
| A slicer with a command line (Bambu Studio, OrcaSlicer, PrusaSlicer) | phase 6 slicing rows | usual install places, `[tools] slicer`, `slicer_kind`; `slicer = "none"` = declined | the rule audit of `print_check.py` still runs; the user slices and sends the previews; the slicer rows read "could not run" (also when the profile's `[slicer]` does not name every preset: nothing is sliced with the slicer's own defaults) |
| Blender | photo renders, manual pictures | `[tools] blender`, `BLENDER`, PATH, usual install places; `blender = "none"` = declined | `views.py` gives plain shaded views; tell the user the pictures are not photo-real. `render_blender.py` still writes its job file |
| Chrome or Edge (headless) | the manual's A4 PDF | usual install places, `[tools] chrome` | `manual_build.py` still writes the HTML; the PDF part exits 2 |
| The browser extension, connected to the session's account | filling forms, the order watch | the session's browser tools | the agent prepares the upload folder and the field sheet; the user types the form and pastes back what the page shows; the agent runs the read-back |
| A fastener library (STEP files) | real screws in the assembly, renders and manual | `[vendor] fasteners` (default `vendor3d/fasteners`) | the fastener rows read "could not run"; no invented cylinders in their place |
| The electronics skill (`electronics-design-jlcpcb`) | `interface.json` generated from the board | the skills folder; `mech/interface.json` with checksums | fill the same file from the maker's STEP or drawing, with the source written in it (`interface-electronics.md` section 6) |
| `uv` (optional) | making Python environments quickly | PATH | use `python -m venv` and `pip` |

## 2. A CadQuery environment with uv

CadQuery brings its own geometry kernel and should live in its own environment, not in the project's Python.

```
uv venv <env folder> --python 3.12
uv pip install --python <env folder>/Scripts/python.exe cadquery numpy shapely ezdxf matplotlib scipy pillow pymupdf vtk
```

On Linux and macOS the interpreter is `<env folder>/bin/python`. Then tell the scripts where it is, once:

```
# <project>/mech/mech.toml
[tools]
cadquery_python = "<env folder>/Scripts/python.exe"
```

or set the environment variable `CADQUERY_PYTHON`. Scripts that need CadQuery re-run themselves under that
interpreter (`mech_common.reexec_with_cadquery`). Suggested place for the environment: a folder of the user's choice
outside the project and outside the skill, so several projects share it. Proven versions: Python 3.12, CadQuery 2.8.
Without `uv`: `python -m venv <env folder>` and `<env folder>/Scripts/python.exe -m pip install ...` with the same list.

Check: `env_check.py --require cadquery,numpy,shapely` exits 0.

## 3. The fastener library recipe

The skill ships no fastener models. Make a library once per user and reuse it:

1. Make a SECOND environment, apart from the CadQuery one. The generator library needs a different build of the
   geometry kernel than CadQuery, and the two do not share an environment:
   `uv venv <fastener env> --python 3.12`, then `uv pip install --python <fastener env>/Scripts/python.exe bd_warehouse`
   (it brings build123d). Version 0.4.0 was used on one project.
2. With a short script in that environment, build each screw, nut, washer and standoff the project uses from the
   library's ISO tables, and export each **twice**: `<id>.step` with the thread helix (for renders and the manual) and
   `<id>_simple.step` without it (a plain envelope, for interference checks and light assemblies).
3. Frame of every file: the axis is z; a screw's bearing face (under the head) is at z = 0 and the shank runs to -z;
   a nut or washer sits on z = 0 and rises to +z.
4. Put the folder at `<project>/mech/vendor3d/fasteners/` (or name it in `[vendor] fasteners`). `vendor_parts.py`
   class `Fasteners` loads from it.
5. Give each `<id>` the standard and size in its name (for example `iso7045_m3x8`), so the parts list and the manual
   read the right thing.

Fan screws and other odd screws with no standard are drawn from the user's measurement (thread, head diameter,
head angle, length) and marked "drawn from a measurement" in the vendor table.

## 4. The slicer

- `print_check.py --slice` copies the presets named in the printer profile (`[slicer] machine, process, filament`
  for Bambu Studio and OrcaSlicer; `config` for PrusaSlicer) to a scratch folder and slices with the copies. The
  user's presets are never opened for writing.
- The command-line options of each slicer were written from their documentation and proven only against a stand-in
  slicer: **verify on the first real run** and correct `[tools] slicer_kind` or tell the user what failed.
- The user must name or export the presets once (phase 1). If they cannot, they slice by hand and send the layer
  previews and the warnings.
- For a soft filament read the printer maker's own guide for the spool path and nozzle before proposing settings.

## 5. Blender

- `render_blender.py` writes STL files, a finish table and a Blender job, then runs Blender in the background:
  Cycles, the GPU when found, all CPU cores otherwise. Proven on Blender 5.x; older versions use a fallback importer.
- Chart colours come from the capability sheets' `[coat_rgb]` and `[ink_rgb]`: approximate.
- Without Blender: `views.py` (shaded views with edges) is the picture set. Say "not photo-real" at the gate.
- Installing Blender is a large download: ask, and download by direct link from the maker's site into its own folder.

## 6. The browser

- The extension must be connected with the same account as the session. Each supplier shop may need its own
  sign-in: the user signs in.
- File uploads read only folders of the session: keep the upload set under the project.
- Mechanics learned on the supplier sites: `suppliers/order-flow.md` section 6.
- Without a browser tool: the agent writes the field sheet and the upload folder; the user fills the form; the user
  pastes the page's text of every field back; the agent compares (`cable_fieldsheet.py --readback`). The order watch
  becomes "the user forwards each supplier mail or pastes the order page".

## 7. The printer profile

Not a tool, but found the same way: `~/.claude/enclosure-cables/PRINTER_PROFILE.toml` in the user's home folder
(outside the skill), created from `templates/PRINTER_PROFILE.toml` only with the user's yes. Without it
`print_check.py` uses defaults (a 220 x 220 x 250 mm bed, 45 degrees, 0.3 mm hole shrink as a first guess) and says
so (the coupon legend reads "default 0.3, not yet measured" until the profile carries a measured value); the
coupon's results replace the guesses.

## 8. What needs no tool at all

Requirements, the process choice, capability sheets, the cable list, the catalogue read of a remark, the order
plan and calendar (`supplier_calendar.py` needs only Python), supplier messages, the arrival plan, reviews of files
someone else made. A project can use these phases with nothing installed but Python.
