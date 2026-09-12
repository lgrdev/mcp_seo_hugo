#!/usr/bin/env python3
"""CLI SEO du plugin lgrdev-mcp-seo. Bibliothèque standard uniquement, aucun `pip install`.

À lancer depuis la racine d'un projet Hugo (le dossier qui contient `content/`).

    python3 seoctl.py audit
    python3 seoctl.py status
    python3 seoctl.py candidates --target blog/2026-03/mon-article.md
    python3 seoctl.py candidates --auto --max 10 --out /tmp/candidats.json
    python3 seoctl.py proposals --from /tmp/choix.json
    python3 seoctl.py apply --dry-run
    python3 seoctl.py archive
    python3 seoctl.py repair
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seolib import config, encoding, proposals as proposals_lib, rank, report  # noqa: E402
from seolib.anchors import insert_link  # noqa: E402
from seolib.content import build_chunks, load_pages, unreadable  # noqa: E402
from seolib.graph import build_site  # noqa: E402


def _load_site():
    pages, skipped = load_pages()
    return build_site(pages, skipped)


def _emit_json(payload, out_path: str | None) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if not out_path:
        return text
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return f"{destination} écrit."


def cmd_audit(args) -> str:
    site = _load_site()
    orphans = site.orphans()
    underlinked = site.underlinked()
    broken = unreadable(site.skipped)
    report_path = report.write_audit_report(site)

    lines = [
        f"Total pages : {site.node_count}",
        f"Total liens internes : {site.edge_count}",
        f"Pages orphelines ({len(orphans)}) :",
    ]
    lines += [f"- Path: {path} | Titre: {site.title(path)} | Slug: {site.slug(path)}"
              for path in orphans]

    if underlinked:
        lines.append(f"\nPages sous-maillées, 1 seul lien entrant ({len(underlinked)}) :")
        lines += [f"- Path: {path} | Titre: {site.title(path)}" for path in underlinked]

    if broken:
        lines.append(f"\nFichiers illisibles, exclus de l'analyse ({len(broken)}) :")
        lines += [f"- {item['path']} : {item['reason']}" for item in broken]
        lines.append("Lance /lgrdev-mcp-seo:repair-seo pour corriger l'encodage.")

    if site.unresolved:
        lines.append(f"\nLiens internes non résolus ({len(site.unresolved)}) : "
                     f"cibles inexistantes ou hors périmètre SEO.")

    lines.append(f"\nRapport HTML : {report_path}")
    return "\n".join(lines)


def cmd_status(args) -> str:
    site = _load_site()
    broken = unreadable(site.skipped)
    chunks = build_chunks(site.pages)

    lines = [f"Contenu : {site.node_count} page(s) dans le périmètre SEO, "
             f"{len(site.skipped)} exclue(s), {len(chunks)} paragraphe(s) exploitable(s).",
             f"Maillage : {site.edge_count} lien(s) interne(s), "
             f"{len(site.orphans())} page(s) orpheline(s), "
             f"{len(site.underlinked())} page(s) sous-maillée(s)."]

    if broken:
        lines.append(f"⚠ {len(broken)} fichier(s) illisible(s), exclus de l'analyse. "
                     f"Lance /lgrdev-mcp-seo:repair-seo.")
    if site.unresolved:
        lines.append(f"⚠ {len(site.unresolved)} lien(s) interne(s) non résolu(s). "
                     f"Détail dans le rapport d'audit.")

    reports = sorted(config.AUDIT_DIR.glob("audit_seo_*.html")) if config.AUDIT_DIR.exists() else []
    lines.append(f"Dernier audit : {reports[-1]}" if reports
                 else f"Dernier audit : aucun rapport dans {config.AUDIT_DIR}/. "
                      f"Lance /lgrdev-mcp-seo:init-seo.")

    if config.PROPOSALS_FILE.exists():
        try:
            pending = proposals_lib.parse_proposals(
                config.PROPOSALS_FILE.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            pending = []
        approved = sum(1 for item in pending if item["approved"])
        applied = sum(1 for item in pending if (item["status"] or "").startswith("APPLIQUÉ"))
        lines.append(f"Propositions en cours ({config.PROPOSALS_FILE}) : {len(pending)} au total, "
                     f"{approved} cochée(s) OUI, {applied} déjà appliquée(s). "
                     f"Poursuis avec /lgrdev-mcp-seo:review-seo.")
    else:
        lines.append("Propositions en cours : aucune. "
                     "Lance /lgrdev-mcp-seo:review-seo pour en générer.")

    return "\n".join(lines)


def cmd_candidates(args) -> str:
    site = _load_site()
    index = rank.Bm25Index(build_chunks(site.pages))

    if args.target:
        targets = [args.target]
        top = args.top or 20
    else:
        targets = site.link_targets()[:args.max]
        top = args.top or 5

    payload = []
    for target in targets:
        if target not in site.pages:
            payload.append({"target_path": target,
                            "error": f"Page cible introuvable : {target}"})
            continue
        payload.append({
            "target_path": target,
            "target_title": site.title(target),
            "target_slug": f"/{site.slug(target)}/",
            "in_degree": site.in_degree(target),
            "candidates": rank.candidates_for(index, site, target, top=top),
        })

    return _emit_json(payload, args.out)


def cmd_proposals(args) -> str:
    """Transforme les choix du juge sémantique en rapport de propositions."""
    picks_path = Path(args.source)
    try:
        picks = json.loads(picks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"Erreur : Lecture impossible de {picks_path} ({exc})."

    if isinstance(picks, dict):
        picks = picks.get("picks", [])
    if not isinstance(picks, list) or not picks:
        return f"Erreur : Aucun choix exploitable dans {picks_path}."

    site = _load_site()
    entries, rejected = [], []
    used = set()

    for pick in picks:
        target = pick.get("target_path")
        source_path = pick.get("source_path")
        paragraph = pick.get("paragraph_text")
        if not (target and source_path and paragraph):
            rejected.append(f"{source_path or '?'} : choix incomplet")
            continue
        if target not in site.pages:
            rejected.append(f"{source_path} : cible inconnue {target}")
            continue
        if (source_path, paragraph) in used:
            rejected.append(f"{source_path} : paragraphe déjà proposé")
            continue

        # Le juge peut reformuler sans le vouloir : un paragraphe absent du fichier
        # ferait échouer l'application plus tard, avec un message moins clair.
        full_path = config.CONTENT_DIR / source_path
        try:
            body = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            rejected.append(f"{source_path} : lecture impossible ({exc})")
            continue
        occurrences = body.count(paragraph)
        if occurrences == 0:
            rejected.append(f"{source_path} : paragraphe introuvable dans le fichier")
            continue
        if occurrences > 1:
            rejected.append(f"{source_path} : paragraphe présent {occurrences} fois, ambigu")
            continue

        new_paragraph, mode = insert_link(paragraph, site.title(target),
                                          f"/{site.slug(target)}/",
                                          anchor_phrase=pick.get("anchor_phrase"))
        used.add((source_path, paragraph))
        entries.append({"source_path": source_path, "target_path": target,
                        "old": paragraph, "new": new_paragraph, "mode": mode})

    if not entries:
        return ("Aucune proposition retenue.\n"
                + "\n".join(f"- {reason}" for reason in rejected))

    report_path = Path(args.out) if args.out else config.PROPOSALS_FILE
    try:
        report_path.write_text(proposals_lib.render_proposals_report(entries), encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Écriture impossible dans {report_path} ({exc})."

    anchors = sum(1 for entry in entries if entry["mode"] == "ancre")
    summary = (f"{len(entries)} proposition(s) écrite(s) dans {report_path} "
               f"({anchors} avec ancre in-prose, {len(entries) - anchors} avec phrase ajoutée).\n"
               f"Coche [x] OUI sur les propositions retenues, puis applique-les.")
    if rejected:
        summary += (f"\n{len(rejected)} choix écarté(s) :\n"
                    + "\n".join(f"- {reason}" for reason in rejected))
    return summary


def cmd_apply(args) -> str:
    report_path = Path(args.file) if args.file else config.PROPOSALS_FILE
    return proposals_lib.apply_approved(report_path, dry_run=args.dry_run)


def cmd_archive(args) -> str:
    report_path = Path(args.file) if args.file else config.PROPOSALS_FILE
    return proposals_lib.archive_report(report_path)


def cmd_repair(args) -> str:
    return encoding.repair(apply=args.apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seoctl", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("audit", help="Audit du maillage interne + rapport HTML").set_defaults(
        handler=cmd_audit)
    subparsers.add_parser("status", help="État du contenu et du maillage, sans rien écrire"
                          ).set_defaults(handler=cmd_status)

    candidates = subparsers.add_parser(
        "candidates", help="Paragraphes candidats pour mailler vers une ou plusieurs cibles")
    group = candidates.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", help="Chemin de la page cible, relatif à content/")
    group.add_argument("--auto", action="store_true",
                       help="Cibles automatiques : pages orphelines et sous-maillées")
    candidates.add_argument("--top", type=int, default=None,
                            help="Candidats par cible (défaut : 20 avec --target, 5 avec --auto)")
    candidates.add_argument("--max", type=int, default=10, help="Nombre de cibles avec --auto")
    candidates.add_argument("--out", help="Écrit le JSON dans ce fichier au lieu de stdout")
    candidates.set_defaults(handler=cmd_candidates)

    proposals_cmd = subparsers.add_parser(
        "proposals", help="Écrit le rapport de propositions à partir des choix retenus")
    proposals_cmd.add_argument("--from", dest="source", required=True,
                               help="JSON des choix du juge sémantique")
    proposals_cmd.add_argument("--out", help=f"Rapport de sortie (défaut : {config.PROPOSALS_FILE})")
    proposals_cmd.set_defaults(handler=cmd_proposals)

    apply_cmd = subparsers.add_parser("apply", help="Applique les propositions cochées OUI")
    apply_cmd.add_argument("--dry-run", action="store_true", help="N'écrit rien, simule")
    apply_cmd.add_argument("--file", help=f"Rapport à lire (défaut : {config.PROPOSALS_FILE})")
    apply_cmd.set_defaults(handler=cmd_apply)

    archive_cmd = subparsers.add_parser("archive", help="Archive le rapport et le réinitialise")
    archive_cmd.add_argument("--file", help=f"Rapport à archiver (défaut : {config.PROPOSALS_FILE})")
    archive_cmd.set_defaults(handler=cmd_archive)

    repair_cmd = subparsers.add_parser("repair", help="Répare l'encodage UTF-8 cassé")
    repair_cmd.add_argument("--apply", action="store_true",
                            help="Écrit les corrections (sinon simulation)")
    repair_cmd.set_defaults(handler=cmd_repair)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not config.CONTENT_DIR.is_dir():
        print(f"Erreur : {config.CONTENT_DIR} introuvable. "
              f"Lance la commande depuis la racine du projet Hugo.", file=sys.stderr)
        return 2

    print(args.handler(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
