// #/job/{jid}/file/{name} — one bundle member as a JSON tree, with a download (M06 design note
// §6, §6.3). Reads the run's bundle listing and the member's exact bytes through the raw export,
// digest-checked against the listing's SHA-256.

import { h } from "../h.js";
import { heading, id, jsonTree, none, num, digestBanner, facts, runBundle, runLinks, section, text } from "./common.js";

export const name = "file";
export const pattern = "/job/{jid}/file/{name}";

export async function load(params, api) {
  const { jid, name: memberName, signal } = params;
  const bundle = await runBundle(api, jid, { signal });
  const member = bundle.files.get(memberName) ?? null;
  if (member === null) return { jid, name: memberName, member: null };
  const read = await api.raw(member.artifact_id, member.sha256, { signal });
  let value;
  let parsed = true;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(read.bytes));
  } catch {
    parsed = false;
  }
  return { jid, name: memberName, member, bytes: read.bytes, digest: read.digest, value, parsed };
}

export function view(data) {
  const head = heading(`${data.name} — ${data.jid}`, ...runLinks(data.jid));
  if (data.member === null) {
    return h(
      "div",
      { "data-ofs-screen": "file" },
      head,
      section("File", none("the bundle of this run has no such file")),
    );
  }
  const onDownload = () => {
    const url = URL.createObjectURL(new Blob([data.bytes], { type: "application/json" }));
    const anchor = globalThis.document.createElement("a");
    anchor.href = url;
    anchor.download = data.name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return h(
    "div",
    { "data-ofs-screen": "file" },
    head,
    digestBanner(data.name, data.digest),
    section(
      "File",
      facts([
        ["name", id(data.member.name)],
        ["kind", text(data.member.kind)],
        ["bytes", num(data.member.size_bytes)],
        ["sha256", id(data.member.sha256)],
        ["digest", data.digest],
      ]),
      h("button", { type: "button", "data-ofs-action": "download", on: { click: onDownload } }, "download"),
    ),
    section(
      "Content",
      data.parsed ? jsonTree(data.value) : none("not JSON: download the file to read it"),
    ),
  );
}
