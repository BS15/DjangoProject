window.mermaidConfig = {
  startOnLoad: true,
  theme: "default",
  securityLevel: "strict",
};

document$.subscribe(function () {
  mermaid.initialize(window.mermaidConfig);
  mermaid.run();
});
