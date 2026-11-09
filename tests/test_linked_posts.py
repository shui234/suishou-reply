"""Every new original has a trusted, copyable link and room for a fuller hook."""
import json

import pytest

from suishou.original import (choose_seed, build_original_messages, parse_post,
                              reference_for_seed, format_post, weighted_length)

BODY = 'AI 写得越快，人就越不能只看结果。🧩 真正容易被省掉的，是边界条件、失败路径和改动理由；这些东西不会因为代码跑通一次就自动补齐。把节省的打字时间分一点给审查，才有机会把生成速度变成可维护的代码，而不是下一轮返工的起点。'


def test_every_inspiration_has_a_reference_and_full_post_ends_in_it():
    from suishou.original import _inspirations
    for item in _inspirations():
        seed = dict(item, style='犀利', topic=item['topics'][0], angle=item['angles'][0])
        source = reference_for_seed(seed)
        assert source['kind'] == 'reference' and source['url'].startswith('https://')
        assert source['summary'] and source['verified_at']
        post = parse_post(json.dumps({'body': BODY, 'source': {'url': 'https://invented.invalid'}}), seed)
        assert post['source']['url'] == source['url']
        assert format_post(post) == BODY + '\n' + source['url']
        assert weighted_length(format_post(post)) <= 280


def test_prompt_asks_for_hook_fuller_body_and_sparing_emoji():
    messages = build_original_messages(choose_seed('幽默', 'AI编程', []), [])
    assert '100—125' in messages[0]['content']
    assert '钩子' in messages[0]['content'] and '1—2' in messages[0]['content']
    assert '参考文档' in messages[0]['content']
    assert json.loads(messages[1]['content'])['source']['kind'] == 'reference'


def test_reference_cannot_be_treated_as_hot_news_and_missing_link_is_explicit():
    seed = choose_seed('犀利', 'AI工具', [])
    source = reference_for_seed(seed)
    with pytest.raises(ValueError, match='热点|新闻'):
        parse_post(json.dumps({'body': BODY}), dict(seed, style='热点'), source)
    with pytest.raises(ValueError, match='链接|来源'):
        format_post({'body': BODY, 'source': None})


def test_link_budget_applies_to_ordinary_posts_and_short_results_are_rejected():
    seed = choose_seed('犀利', 'AI工具', [])
    with pytest.raises(ValueError, match='长度|280'):
        parse_post(json.dumps({'body': '中' * 129}), seed)
    with pytest.raises(ValueError, match='长度'):
        parse_post(json.dumps({'body': '中' * 60}), seed)
    assert parse_post(json.dumps({'body': '中' * 126 + '🧩'}), seed)['body'].endswith('🧩')


def test_unknown_local_reference_does_not_invent_a_link():
    with pytest.raises(ValueError, match='参考|来源'):
        reference_for_seed({'id': 'not-in-catalog'})
