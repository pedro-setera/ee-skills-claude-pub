# EE skills for Claude Code

Two skills that let [Claude Code](https://claude.com/claude-code) take an electronic device from a first idea to real parts on your desk: the circuit and the PCB, then the enclosure and the cables, ordered at **JLCPCB**, **LCSC** and their sister services.

They are not prompts. Each skill is a gated engineering process with its own rules, checklists, review briefs and Python scripts, written from the mistakes of real projects: a transistor placed rotated, a connector over a screw, a cable a few millimetres short, a value that could not be changed after the order. Each check exists because skipping it once cost days or boards.

| Skill | What it does | It starts when you ask for |
|---|---|---|
| [`electronics-design-jlcpcb`](skills/electronics-design-jlcpcb/SKILL.md) | Circuit and PCB: requirements, architecture, part selection, schematic, SPICE simulation, KiCad layout, independent reviews, production files, the order of assembled boards, the order watch and the first power-up | a circuit, a schematic, a PCB, a review of a board, an order at JLCPCB |
| [`enclosure-cables-jlc`](skills/enclosure-cables-jlc/SKILL.md) | Enclosure and cables: a parametric 3D model in code, a printed concept box first, then sheet metal or CNC parts with fully dimensioned drawings; custom cables measured in the same 3D model; the orders and the fit check on arrival | a box, a case, a front panel, a printed enclosure, cables or harnesses |

The two skills hand over to each other: the electronics skill exports the board (outline, holes, connectors, heights), and the enclosure skill sends back keep-outs, connector exits and cable lengths.

You can use the whole flow, or only one step: a review of a design you already have, only the production files, only the cables, only an order that needs watching.

## Suppliers: these skills are written for the JLC group

The rules, forms, file formats and order steps in these skills are those of specific suppliers. This is on purpose: a skill that knows one supplier well makes fewer mistakes than one that knows every supplier a little.

| Job | Supplier |
|---|---|
| PCB fabrication and assembly (assembled sample boards) | **JLCPCB** |
| Part search, stock, price, datasheets, loose parts | **LCSC**, and JLCPCB's own parts library for the assembly stock |
| Custom cables, wire harnesses, coax and network cables | **LCSC Cable** |
| Sheet-metal and CNC-machined enclosure parts, powder coat, anodizing, silkscreen | **JLCCNC** |
| 3D-printed parts | your own FDM printer first, or **JLC3DP** |

Supplier rules change. The skills carry the rules as they were read in November 2026, each with its date, and they re-read the live pages before an order. You need your own accounts at these suppliers. This project is **not affiliated with, sponsored by or endorsed by** JLCPCB, LCSC, JLCCNC, JLC3DP, the KiCad project or Anthropic.

## How it works

- **You stay in charge.** The work is cut into phases with a few approvals by you: the device description, the schematic with its parts cost, the board, the payment. The agent asks few questions, each with a suggested answer and its reason.
- **Independent reviews.** Fresh agents, which did not design the board, review the circuit, the board (one from the files, one from the pictures alone) and the order files against the supplier's rules. One fix round, one re-check, then the open points come to you as named risks.
- **Checks by script, then by eye.** Scripts check connectivity, pin ratings, placement angles, copper, silkscreen, clearances and the freshness of the order files. Then the agent has to open the pictures and say what it sees.
- **The agent never pays.** It prepares each order up to the cart or the payment page. The button that creates a board order is yours. A quote request, or parts sent for the supplier's review, is your click too, or the agent's only after your go on that exact cart. You pay.
- **A human pace at the suppliers' sites.** One request at a time, saved answers reused, and a full stop at the first refusal. Live look-ups need your yes.
- **State on disk.** Every project keeps a state file, so a long job survives a lost session.

## What you need

**Claude**

- **Claude Code**: the command line, the Code tab of the desktop app, or an IDE extension.
- **Model:** the most capable Claude model you can get. The skills were built and tested with **Claude Fable 5.2**; use that or any newer, more capable model. Smaller models skip steps and miss faults.
- **Effort:** **extra high** (`xhigh`). The reviews are told to run at the highest effort.
- **Plan:** we suggest the **Ultra plan** (USD 200 per month in November 2026). A full design uses many agents for many hours; on a smaller plan the usage limits run out quickly.
- **Time:** expect **many hours**, and this is normal. In our own test, a simple 50-part, 2-layer board took about six and a half hours of agent work from the finished schematic to the order files, with three questions to the user. A device from the first idea, or a harder board, takes longer. Plan to let it run and to answer a question now and then.

**Software on your computer**

| For | You need | Optional |
|---|---|---|
| Both skills | Python 3.11 or newer; a browser extension that lets Claude use your signed-in browser (Claude in Chrome) for the supplier pages. Without it the agent prepares the files and a click-by-click list, and you click | scheduled tasks and push notifications for the order watch |
| `electronics-design-jlcpcb` | KiCad 9 or 10 (it brings `kicad-cli`, its own Python and the ngspice simulator); numpy, matplotlib, Pillow | CadQuery (3D body checks), easyeda2kicad (JLCPCB's footprints, needed to derive placement angles), SciPy and scikit-rf (RF filters), LTspice, poppler |
| `enclosure-cables-jlc` | CadQuery in its own Python environment; numpy, shapely, ezdxf, matplotlib, scipy, Pillow, PyMuPDF, vtk | a slicer with a command line (Bambu Studio, OrcaSlicer, PrusaSlicer), Blender for photo renders, Chrome or Edge for the PDF manual, a fastener library |

Each skill starts by running its own environment check and tells you what is missing. It asks before installing anything. What each tool is for, and what the skill does without it, is in each skill's `references/tools.md`.

## Install

1. Copy both folders under [`skills/`](skills/) into your personal skills folder:
   - Windows: `C:\Users\<you>\.claude\skills\`
   - macOS and Linux: `~/.claude/skills/`
2. Start a **new** Claude Code session. The skills are found by themselves.
3. Set the model and the effort (see above).

With git:

```bash
git clone https://github.com/pedro-setera/ee-skills-claude-pub.git
```

then copy `ee-skills-claude-pub/skills/electronics-design-jlcpcb` and `ee-skills-claude-pub/skills/enclosure-cables-jlc` into the skills folder.

## First use

Open a session in an empty project folder and say what you want, in your own words. For example:

- "I want a small board that switches a 12 V fan on above 35 °C, in a small aluminium case. Five boards, assembled."
- "Here is my KiCad project. Review it before I order, and change nothing."
- "I have Gerbers, a BOM and a placement file. Check them against JLCPCB's rules and prepare the order."
- "Design a printed box for this board and its display, then the cables between them."
- "My order has a question from the manufacturer's engineer. Help me answer it."

The skill then asks its first questions. Answer in plain words; you do not need to be an electronics engineer for the questions, but someone who is should look at the result before you rely on it (see the safety note).

## Status and limits

This is an early release. Please read this before you trust it with money.

- **`electronics-design-jlcpcb`:** all its script test suites pass, and it carried one complete test board (a 50-part fan controller) to order files, which an independent judge found at least as good as the same board made without the skill. It has been through an independent review and a final read-only pass, and their findings are fixed. **No real order has been placed with the final version yet.** What it is built for: boards up to 6 layers with microcontrollers, analog circuits, power conversion, sensors, USB 2.0 and simple 50 ohm RF. Memory buses, fine-pitch BGA, multi-gigabit links and mains voltage are beyond it.
- **`enclosure-cables-jlc`:** tried on small and medium boxes printed on a home FDM printer, and on folded aluminium sheet and custom cables **up to the order and the supplier's review**. The delivered parts are not measured yet; the sections that wait for that evidence are marked **PROVISIONAL** in the files.
- **Operating system:** developed and tested on **Windows 11** only. The scripts are plain Python and look for their tools on macOS and Linux too, but nobody has run them there.
- **Tests:** the test suites are not in this repository, because their fixtures are private designs. The scripts you get are the tested ones; for this public copy only comments, a few printed texts and example values were changed.
- **The suppliers can change** a rule, a form or a price at any time. The skills re-read the live pages, but a surprise is always possible: read what the agent shows you before you pay.

## Safety note

Electronics can hurt people and start fires. These skills help an AI agent design hardware; they do not replace an engineer.

- Have a **qualified engineer** check anything that carries mains voltage, charges or holds lithium cells, drives real power, or whose failure could hurt someone, before you build or power it.
- A board that passes every check here is a **prototype**. It is not tested for safety, emissions or any market's regulations.
- You are responsible for what you order, build and switch on. The software and the documents come **without any warranty**; see the [licence](LICENSE).

## Contributing

Improvements are welcome: a rule that is wrong, a supplier form that changed, a lesson from your own board, a script that fails on your system.

- Open an **issue** to report a problem or propose an idea. Say which skill, which file, and what happened.
- Open a **pull request** for a concrete change. Keep it small and say what real failure it prevents.
- Changes are tested in a private build with the full test suites before they appear here, so an accepted change can take a little while to show up.
- Please put no private data in an issue or a pull request: no order numbers, addresses or design files you may not share.

## Author

**Pedro Silva**, Portugal. I am a hardware engineer and I built these skills together with Claude.

If this work is useful to you, if you have an idea for it, or if you would like to work with me on a hardware project, write to me: **pedro.lps.pt@gmail.com**

## Licence

[MIT](LICENSE). You may use, change and share these skills, also commercially, as long as the copyright notice stays with them.

JLCPCB, LCSC, JLCCNC, JLC3DP, KiCad, Claude and the other names used here are trademarks of their owners and are used only to say what the skills work with.
