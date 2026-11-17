# Working rules

Read once per session, before the first phase. These rules hold in every phase. Each exists because breaking it
cost time on a real project.

## 1. Talking to the user

- **Short. Conclusion first.** Lead with the conclusion and the one action needed from the user. Then a short
  done / left list. Then the exact path of every file named. Long narratives lose the user.
- **Everyday words.** Assume the user is not a mechanical engineer. Say what a choice means for the device, its cost
  and its look.
- **Pictures.** Show a picture wherever one exists: a layout, a render, a zoomed crop of the risk. Before heavy work
  show a simple mock-up or a 2 to 3 variant study and let the user pick.
- **The question shape:**

  ```
  <the question, one line>
  Suggested: <the answer you would choose>
  Why: <one line>
  ```

  At most about five questions in a round of phase 1 or 2; at most three decisions in any other message. Ask only
  what a datasheet, the model or the supplier's site cannot answer.
- **Ask once.** Choices of cable ends, routes, cable types, colours, inks and wording are asked once, before any
  drawing, and written in the state file with the date and the user's words.
- **Milestones.** Tell the user when something is ready for them: print files, a gate, a payment step, a supplier
  question. Do not go silent during long work: one line when a long step starts and when it ends.
- **No confident claim without a look.** A claim the user can disprove by opening the model costs trust.

## 2. An opinion asked is not a go

When the user asks "what do you think?", "analyse this", "would it be better if": answer, recommend, and wait. Change
nothing until they say go. For heavy work (a redesign, a render set) say the plan first and wait for the approval.

## 3. Never without the user

Installing software. Sign-in. Card data, payment, the final submit. Terms and consent boxes. Sending any e-mail,
chat line or revision note they have not seen (a standing OK per order counts when it is recorded in the state
file). Confirm on a production drawing. Accepting a supplier's proposed change. Changing their slicer settings.
Starting a print. Buying anything. Creating a folder in their home folder. Writing into this skill.

If the tool's safety system blocks a click, stop there and hand over. Never work around it.

## 4. Suppliers

- Order only what the forms and charts offer. One value per item. No questions in files.
- Do not send question lists. Design to the conservative side and let their review speak.
- Do not ask what their site already says.
- Answer only what is asked, for that part or line, in the same thread, in their words.
- No product, board or personal names in anything a supplier sees: End A / End B, P1 / P2, part numbers.
- Work to their working day (`supplier_calendar.py`).
- **Supplier sites at a human pace.** One agent on a site at a time. Load a page, let it finish, read it, save its
  text, work from the copy. No bursts, no loops, no parallel tabs hammering one site. At a refusal, a bot check,
  "too many requests" or an empty page: stop all access to that site, write it down, tell the user. Never solve or
  bypass a bot check.
- Details: `suppliers/order-flow.md`, `suppliers/after-order.md`.

## 5. Agents

- **Brief with files.** A brief names the goal, the files to read (absolute paths), what is already ruled out, the
  rules, the output files and their place. It is the only context the agent has. Review briefs are ready in
  `review-briefs/`: fill the slots, send the brief whole.
- **The most capable model at the highest effort** for all engineering work (modelling, drawings, cable data,
  reviews), set explicitly in every agent call and written in its report. Cheaper models only for mechanical work
  such as file conversion.
- **Progress files.** Every agent that runs longer than a few minutes keeps `<name>_PROGRESS.md` (done, in work,
  left) and writes results to disk as it goes.
- **No stale or hung agents.** After each report, list the agents that are running. An agent whose progress file has
  not moved is checked, then stopped. Before telling the user "done", make sure nothing forgotten is still running.
- **At most 2 strong agents at a time** unless the state file says otherwise. Start the next when one reports.
- **Designers and reviewers are different agents.** A reviewer gets files, never conclusions.
- An agent's report is a claim. Open the files it names before repeating the claim to the user.
- Put the standing rules into every brief: no browser download clicks, no supplier messages, no installs, no private
  data, use all cores, write progress.

## 6. Files

- **One output folder.** Everything generated lives under `<project>/mech/out/` (`step/`, `views/`, `renders/`,
  `drawings/`, `silk/`, `cables/`, `print/`, `checks/`, `upload/<supplier>/`). Never a second folder with older copies.
- **One build, nothing stale.** After any change run `build.py`: it regenerates everything and fails on a file older
  than its inputs. A change to one part changes the STEP, the assembly, the views, the renders, the drawings, the
  cable lengths and the manual pictures: all of them, or none is handed over.
- **Say exact paths.** Every message that names a file gives its full path in one piece. "The new renders are
  ready" without the folder brings the question "where?".
- **Remove stale files.** Delete or archive superseded outputs in the same step that makes the new ones. Frozen
  copies of what was reviewed or ordered are the exception: they stay, in `reviews/frozen/` and `orders/`, read-only.
- **In the user's folder.** Files the user will open are in the project folder they work in, not in a temp folder
  or an agent's scratch space.
- **No number typed twice.** Board numbers from `interface.json`; cable lengths from the model; drawings from the
  exported STEP; form values from the field sheet.
- **State on disk.** Decisions go into `PROJECT_STATE.md` as they are made, with the date and the user's words.
  A session that loses its context reads one file and continues.
- **Never write into the skill folder.** Lessons go to the project; a proposal for the skill goes to the user
  (phase 16).

## 7. Downloads

By direct link only, with a command, into the download's own new folder, with the source address and the licence
noted (`vendor3d/vendor_parts.toml` holds both per model). Never a click on a download button in a browser: a save
dialog opens that nobody can answer. If there is no direct link, give the user the page and ask them to save the
file into the named folder. Read what was downloaded before using it. Do not run code from a download.

## 8. Computing

- **Use all CPU cores** for heavy checks, slicing, drawing books and renders (`MECH_WORKERS` or all cores), with
  progress output, and with the same results as a serial run. Use the GPU for renders when Blender finds one.
- **One heavy job at a time per kind** when jobs share files (two builds into one `out/` folder corrupt each other).
- A long job prints progress; a silent long job looks hung.
- Call scripts as `python -I <skill folder>/scripts/<name>.py`. Scripts that need CadQuery re-run themselves under
  the interpreter named in `[tools] cadquery_python` or `CADQUERY_PYTHON`.

## 9. Evidence

- Every check ends pass, fail, could not run or not applicable, with its proof. A check that cannot run is never
  a pass. Headlines count the four apart.
- Supplier rules are measured on the exported STEP, DXF and PDF, not on design parameters.
- **Look.** Open every view, render, drawing page, slicer preview, ink sheet and cable drawing and write what was
  seen. Zoom on each hole, connector, cut-out, label and vent group.
- Never invent a fact. A dimension, a rule value, a part number, a price, a lead time comes from a source opened in
  this project, or it is UNKNOWN. A measurement nobody has is asked from the user with a sketch.
- Supplier facts carry a date. Before an order an independent agent re-reads the live pages.

## 10. Economy

The cheapest standard part and process that meets the requirement first: a bought standard case before a custom
one, a plain rectangle before a shaped part, chart colours before special ones, parts the user already owns before
new ones. No tooling. Do not add what was not asked for: offer it with its cost. Check live stock before choosing a
part. Do not buy for a concept what is only needed for the product.

## 11. Privacy

- No private data in this skill, in a script, in a template, or in anything uploaded: no personal names, e-mail
  addresses, phone numbers, street addresses, account names, order numbers.
- Scrub STEP headers (`step_scrub.py`) and scan every upload folder (`privacy_scan.py`) before the freeze. CAD
  kernels write the PC's user and host name into file headers.
- The company name in drawings and headers comes from `[project] company`; never a person's name.
- Supplier messages and pictures carry no product or board names.
- The user's printer profile and preferences live in their home folder, outside the skill, created only with
  their yes.
- Lessons proposed for the skill (phase 16) are rewritten without names, numbers of orders or project words, and go
  in only with the user's OK on each line.
