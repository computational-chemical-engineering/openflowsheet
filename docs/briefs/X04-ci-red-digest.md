X04 CI run 42624006442 at 4c818959 — both archs: 7 failed, 19632 passed (arm). default-install: collection error.
1. tests/test_m02_schemas.py:274 test_..._without_m02s_additions_every_response_is_its_pre_m02_snapshot — submit_job
   digest c88d59cf… != 0cd08fb1… (strip chain without_m04(without_msg(without_x02(without_opt(...)))) lacks without_x04;
   X04's job_result root `display_units` reaches submit_job's resolved response).
2. tests/test_m04_study_job.py:293 test_a42_m04s_responses_decompose_onto_m02s_snapshots — submit_job 80c13677… !=
   e9abdbeb… (same: chain lacks without_x04).
3. tests/test_t08_b50_surface_content.py:159 (get_project differs: ambient_pressure), :234 (['get_project…vals
   differs']), :245, :255 (test_m07a_a51_b / a51_c: models list message differs) — X04's surface not registered in
   B50's content check.
4. tests/test_t08_w2_description_reviews.py:52 — 2 human pending (expected until Frank's script).
5. default-install: tests/test_x04_messages.py:35 imports openflowsheet.application.bindings.mcp → `import anyio`
   (absent in the default install) → collection error. Other MCP-using tests guard with importorskip/skip markers.
