/* Builds the single-file hosted version (claude.ai artifact) from ./public.
 * Usage: node build-artifact.js <out.html>   — uses the artifact database instead of the Node server. */
const fs = require("fs");
const r = (f) => fs.readFileSync(__dirname + "/public/" + f, "utf8");
const body = r("index.html").split("<body>")[1].split("</body>")[0].replace(/<script[^>]*><\/script>/g, "").trim();
const out = `<title>HR-02 Lifecycle Agent</title>
<style>
${r("style.css").replace(":root {", ":root {\n  color-scheme: dark;")}
</style>
${body}
<script>
${r("agent.js")}
</script>
<script>
${r("actions.js")}
</script>
<script>
${r("backend-db.js")}
</script>
<script>
${r("app.js")}
</script>
`;
fs.writeFileSync(process.argv[2] || "artifact.html", out);
console.log("wrote", process.argv[2] || "artifact.html", out.length, "bytes");
