import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const sourcePath = process.argv[2]
  ?? "D:/Escritorio/MyPage/manuelma4.github.io/assets/js/content.js";
const outputPath = path.join(projectRoot, "app", "data", "profile_seed.json");

const context = { window: {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context, {
  filename: sourcePath,
});

if (!context.window.SITE) {
  throw new Error("The portfolio file did not expose window.SITE");
}

const site = JSON.parse(JSON.stringify(context.window.SITE));
const profile = {
  schema_version: 1,
  imported_at: new Date().toISOString(),
  source: {
    kind: "portfolio",
    path: sourcePath,
    note: "Automatic snapshot. Re-run scripts/import_portfolio.mjs to refresh.",
  },
  person: site.meta,
  summaries: site.about,
  education: site.education,
  experiences: site.experience,
  projects: site.projectCatalog,
  skills: site.skills,
  certifications: site.certifications,
  languages: site.languages,
  preferences: {
    target_roles: [
      "Data Engineer",
      "AI Engineer",
      "Data & AI Software Engineer",
      "Software Engineer",
    ],
    locations: ["Paris", "France", "Europe", "Remote"],
    default_document_language: "auto",
    include_all_background_in_profile: true,
  },
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(profile, null, 2)}\n`, "utf8");
console.log(`Imported portfolio profile to ${outputPath}`);

