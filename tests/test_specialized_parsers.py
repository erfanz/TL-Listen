import re
import unittest

import config
from parsers import parse_specialized_email_stories
from summarize import split_email_stories

_ROBINHOOD_EMAIL = {
    "from": "Robinhood Snacks <hello@snacks.robinhood.com>",
    "html": """
<span><span><strong>CHARGE</strong></span></span>
<h1><a><strong>After a big pullback for EVs, climbing gas prices are causing drivers to eye them again</strong></a></h1>
<p> Gas prices in the US have climbed <a><strong>$0.60 in less than two weeks</strong></a> because of the war with Iran. Prediction markets are pricing in an implied 62% chance that the price of gas exceeds $4 by the end of the month. That has EVs once again turning car shoppers’ heads, <a><strong>though the EV landscape is very different</strong></a> than it was the last time oil prices spiked. </p>
<ul><li>A person familiar with car sales across the US told Sherwood News that they’ve seen EV order growth significantly outpacing the non-EV baseline, as consumers’ EV interest has risen over the past several days.</li><li>A spokesperson for auto retailer <a><strong>CarMax</strong></a> told Sherwood that the company has recently observed a “statistically significant lift in shoppers searching for EVs, Hybrids, and Plug-In Hybrids.”</li></ul>
<p> EVs saw elevated interest from rising gas prices then, with some even selling on the secondary market for more than retail consumers on waitlists had bought them for.</p>
<p>Today, the EV market has matured and gone through a pullback. The Trump administration eliminated the tax credit and revoked the 50% EV sales target. But the sheer number of EVs available has also grown immensely in that time, driving growth in used EV sales.</p>
<h1><span>THE TAKEAWAY</span></h1>
<p> At those used prices, EVs may be of more interest to cost-weary shoppers. The trend has already begun: in January, used EV sales grew 21% from a year earlier, while new EV sales fell 30%, Cox data shows. Sales could continue to swing toward cheaper used EVs if gas prices remain elevated. If prices remain elevated in the long term, however, <a><strong>that story could change</strong></a>. </p>
<p> “While higher gas prices do tend to refocus shoppers on fuel economy, the near-term impact is more likely to show up in household behavior than in vehicle purchase behavior,” said Stephanie Valdez-Streaty, Cox Automotive’s director of industry insights. “To materially change buying behavior and drive a trend toward smaller, more efficient vehicles, <a><strong>consumers would need to believe gas prices will remain elevated for years, not just months</strong></a>.” </p>
<a><span><span><strong>Read more</strong></span></span></a>
<p>*Event contracts are offered through <span><span>Robinhood</span></span> Derivatives, LLC — probabilities referenced or sourced from KalshiEx LLC or ForecastEx LLC.</p>
<span><span><strong>ZOOM OUT</strong></span></span>
<h1><span>Stories we’re obsessed with</span></h1>
<ul><li><a><strong>Markets are pricing in a longer oil supply crunch</strong></a></li></ul>
<span><span><strong>THE BEST THING WE READ TODAY</strong></span></span>
<h1><a><strong>Google Maps is getting a new AI-powered “Ask Maps” feature</strong></a></h1>
<p> On Thursday, <a><strong>Google</strong></a> announced that it would be integrating <a><strong>Gemini</strong></a> into Google Maps. As the gap between Google Maps and <a><strong>Apple</strong></a> Maps narrows, Alphabet is clearly hoping Gemini can provide the answers moving forward: the new “Ask Maps” feature will allow users to ask more sophisticated questions in the Google Maps app, providing chill-sounding use cases like, “My friends are coming from Midtown East to meet me after work. Any spots with a cozy aesthetic and a table for 4 at 7 tonight?” </p>
<p><a><strong>Google Maps vs. Apple Maps</strong></a></p>
<h1><span><span><span>Snacks</span></span> Shots</span></h1>
<p>For more March Madness coverage, <a><strong>subscribe to Scoreboard</strong></a>, our sports newsletter.</p>
""",
}


class SpecializedParserTests(unittest.TestCase):
    def setUp(self):
        self.original_rules = config.CONTENT_PARSER_SENDER_RULES
        self.original_min_words = config.EMAIL_STORY_MIN_WORDS

    def tearDown(self):
        config.CONTENT_PARSER_SENDER_RULES = self.original_rules
        config.EMAIL_STORY_MIN_WORDS = self.original_min_words

    def test_uses_configured_robinhood_parser_for_matching_sender(self):
        config.CONTENT_PARSER_SENDER_RULES = [
            (re.compile(r"snacks\.robinhood\.com", re.IGNORECASE), "robinhood")
        ]

        stories = split_email_stories(_ROBINHOOD_EMAIL, email_subject="Robinhood Snacks")

        self.assertEqual(len(stories), 2)
        self.assertEqual(
            [story["title"] for story in stories],
            [
                "After a big pullback for EVs, climbing gas prices are causing drivers to eye them again",
                'Google Maps is getting a new AI-powered "Ask Maps" feature'.replace('"', "“", 1).replace('"', "”", 1),
            ],
        )
        self.assertTrue(stories[0]["text"].startswith("Gas prices in the US have climbed"))
        self.assertIn(
            "consumers would need to believe gas prices will remain elevated for years, not just months",
            stories[0]["text"],
        )
        self.assertNotIn("Read more", stories[0]["text"])
        self.assertNotIn("Event contracts are offered", stories[0]["text"])
        self.assertNotIn("Stories we’re obsessed with", stories[0]["text"])
        self.assertTrue(stories[1]["text"].startswith("On Thursday, Google announced"))
        self.assertIn("table for 4 at 7 tonight?", stories[1]["text"])
        self.assertNotIn("Google Maps vs. Apple Maps", stories[1]["text"])
        self.assertNotIn("Snacks Shots", stories[1]["text"])

    def test_skips_specialized_parser_without_matching_sender_rule(self):
        config.CONTENT_PARSER_SENDER_RULES = [
            (re.compile(r"example\.com", re.IGNORECASE), "robinhood")
        ]

        stories = parse_specialized_email_stories(_ROBINHOOD_EMAIL)

        self.assertEqual(stories, [])

    def test_finds_story_headings_when_nested_in_other_tags(self):
        config.CONTENT_PARSER_SENDER_RULES = [
            (re.compile(r"snacks\.robinhood\.com", re.IGNORECASE), "robinhood")
        ]
        config.EMAIL_STORY_MIN_WORDS = 20
        nested_email = {
            **_ROBINHOOD_EMAIL,
            "html": """
            <section>
                <div>
                    <h1><a><strong>After a big pullback for EVs, climbing gas prices are causing drivers to eye them again</strong></a></h1>
                </div>
                <article>
                    <p>Gas prices in the US have climbed rapidly, and EV shoppers are paying attention again. This paragraph adds enough words to stay above the story threshold while keeping the sample compact and realistic.</p>
                    <p>Stephanie Valdez-Streaty said consumers would need to believe gas prices will remain elevated for years, not just months, to materially change buying behavior toward smaller and more efficient vehicles.</p>
                </article>
            </section>
            <div>
                <aside><h1><span>THE BEST THING WE READ TODAY</span></h1></aside>
                <section>
                    <div><h1><a><strong>Google Maps is getting a new AI-powered “Ask Maps” feature</strong></a></h1></div>
                    <p>On Thursday, Google announced Gemini in Maps and pitched more conversational planning questions, including whether there is a cozy place with a table for 4 at 7 tonight.</p>
                </section>
            </div>
            """,
        }

        stories = split_email_stories(nested_email, email_subject="Robinhood Snacks")

        self.assertEqual(len(stories), 2)
        self.assertEqual(
            stories[0]["title"],
            "After a big pullback for EVs, climbing gas prices are causing drivers to eye them again",
        )
        self.assertIn("gas prices will remain elevated for years, not just months", stories[0]["text"])
        self.assertEqual(
            stories[1]["title"],
            'Google Maps is getting a new AI-powered "Ask Maps" feature'.replace('"', "“", 1).replace('"', "”", 1),
        )
        self.assertIn("table for 4 at 7 tonight", stories[1]["text"])

    def test_parses_mixed_h1_strong_and_h1_link_strong_titles(self):
        config.CONTENT_PARSER_SENDER_RULES = [
            (re.compile(r"snacks\.robinhood\.com", re.IGNORECASE), "robinhood")
        ]
        config.EMAIL_STORY_MIN_WORDS = 80
        mixed_email = {
            "from": "Robinhood Snacks <hello@snacks.robinhood.com>",
            "html": """
            <h1><a><strong>Google releases blockbuster white paper that spells quantum uncertainty for a whole lot of bitcoin</strong></a></h1>
            <p>Google researchers sent a wake-up call Tuesday, saying quantum machines will require fewer resources in the future to break classical cryptography.</p>
            <ul>
                <li>This is a big deal for stuff like bitcoin, which depends on blockchain cryptography remaining difficult to break.</li>
                <li>The paper described a meaningful reduction in the resources needed to attack those systems.</li>
            </ul>
            <h1><span>THE TAKEAWAY</span></h1>
            <p>Researchers still think there is time to migrate to post-quantum cryptography, but the window may be shorter than the market expects.</p>
            <h1><strong>Silver is in the spotlight. Here's a smarter way to explore it.</strong></h1>
            <p>Silver is a critical industrial input powering solar panels, EVs, and the broader energy transition.</p>
            <p>Junior silver miners offer a distinct way to gain exposure to the precious metals market.</p>
            <h1><a><strong>The Iran war oil shock gave the markets ’70s stagflation vibes</strong></a></h1>
            <p>Oil and commodities stocks soared while bonds and growth favorites struggled over the last month.</p>
            <h1><span>THE TAKEAWAY</span></h1>
            <p>Dividend-paying value stocks have started to look more attractive in a stagflationary backdrop.</p>
            <h1><a><strong>OpenAI is now valued at $852 billion</strong></a></h1>
            <p>OpenAI closed a massive funding round that valued the company at $852 billion, even though the brief is shorter than the generic minimum story threshold.</p>
            <p><a><strong>Worth how many Disneys?</strong></a></p>
            <h1><strong>Snacks Shots</strong></h1>
            <ul><li>This roundup should not be treated as a standalone story.</li></ul>
            """,
        }

        stories = split_email_stories(mixed_email, email_subject="Robinhood Snacks")

        self.assertEqual(
            [story["title"] for story in stories],
            [
                "Google releases blockbuster white paper that spells quantum uncertainty for a whole lot of bitcoin",
                "Silver is in the spotlight. Here's a smarter way to explore it.",
                "The Iran war oil shock gave the markets ’70s stagflation vibes",
                "OpenAI is now valued at $852 billion",
            ],
        )
        self.assertIn("post-quantum cryptography", stories[0]["text"])
        self.assertIn("energy transition", stories[1]["text"])
        self.assertIn("stagflationary backdrop", stories[2]["text"])
        self.assertIn("valued the company at $852 billion", stories[3]["text"])
        self.assertIn("Worth how many Disneys?", stories[3]["text"])
        self.assertNotIn("Read the Full Report", stories[1]["text"])

    def test_saved_robinhood_email_extracts_expected_story_boundaries(self):
        config.CONTENT_PARSER_SENDER_RULES = [
            (re.compile(r"snacks\.robinhood\.com", re.IGNORECASE), "robinhood")
        ]
        email = {
            "from": "Robinhood Snacks <hello@snacks.robinhood.com>",
            "html": """
            <h1><a><strong>Google releases blockbuster white paper that spells quantum uncertainty for a whole lot of bitcoin</strong></a></h1>
            <p>Google researchers sent a wake-up call Tuesday, saying quantum machines will require fewer resources in the future to break classical cryptography.</p>
            <ul>
                <li>This is a big deal for stuff like bitcoin, which is predicated on the idea that blockchain cryptography will remain sufficiently difficult to break for the foreseeable life of the asset.</li>
                <li>“The emergence of CRQCs [cryptographically relevant quantum computers] represents a serious threat to cryptocurrencies that demands a close examination of possible developments at the intersection of quantum computing and digital finance,” Google’s white paper says.</li>
                <li>The analysis showed a twentyfold reduction in the amount of resources needed by a quantum machine to break the cryptography backing blockchain networks.</li>
                <li>The paper continued, “While the quantum computing and cryptocurrency communities have largely operated in isolation, the significant reduction in resource requirements detailed here necessitates a convergence of these two worlds.”</li>
            </ul>
            <p>“Their fast-clock architecture could crack a private key in 9 minutes, while bitcoin blocks take 10 minutes on average. That changes the threat model entirely,” Alex Pruden, CEO and cofounder of quantum computing research firm Project Eleven, told Sherwood News. “Every bitcoin transaction is at risk.”</p>
            <h1><span>THE TAKEAWAY</span></h1>
            <p>While a quantum computer capable of successfully exploiting a blockchain does not exist yet, Google researcher Craig Gidney has placed a 10% chance one will be built by 2030. Meanwhile, Google landed on a 2029 timeline to migrate its infrastructure to post-quantum cryptography.</p>
            <p>Not only are 6.7 million bitcoin — including those believed to belong to bitcoin’s pseudonymous creator, Satoshi Nakamoto — vulnerable to future quantum attacks, but so are the protocols underlying the tokenization market of real-world assets, which, the paper projects, will exceed $16 trillion by 2030.</p>
            <h1><strong>Silver is in the spotlight. Here's a smarter way to explore it.</strong></h1>
            <p>Silver isn't just a store of value — it's a critical industrial input powering solar panels, EVs, and the global energy transition.</p>
            <p>And demand continues to grow.</p>
            <p>Junior silver miners offer investors a distinct way to gain exposure to the precious metals market — one that goes beyond simply holding the physical metal.</p>
            <p>Nasdaq’s latest research explores the Nasdaq Junior Silver Miners™ Index (NMFSM™) and how junior silver miners offer unique growth potential.</p>
            <p>Learn about:</p>
            <ul>
                <li>Silver's demand and supply dynamics</li>
                <li>How silver compares to gold</li>
                <li>The potential benefits and risks of investing in junior silver miners</li>
            </ul>
            <p><a><strong>Read the Full Report →</strong></a></p>
            <p><em>Indexes are not directly investable. Past performance is not indicative of future results. Investing involves risk, including possible loss of principal.</em></p>
            <h1><a><strong>The Iran war oil shock gave the markets ’70s stagflation vibes</strong></a></h1>
            <p>Oil and commodities stocks soared. Value stocks outperformed growth favorites. And stocks and bonds, broadly, sank in lockstep over the last month. Heck, even dividends — a tried-and-true defense against both inflation and lousy market performance — are showing signs of coming back into favor.</p>
            <p><a><strong>A wartime whiff of stagflation permeated the markets in March</strong></a>.</p>
            <ul>
                <li>“If the conflict persists, the combination of slower growth and higher inflation would create a stagflationary environment, historically the worst backdrop for equities,” analysts with Ned Davis Research wrote in a report published Tuesday.</li>
                <li>The 1970s were a particularly brutal decade for stocks. The S&amp;P 500 rose just 17% during those 10 years — about as much as the market gains in a single average positive year — as multiple Mideast oil supply shocks and large government debt kept inflation at an average of 7%, sometimes much higher.</li>
                <li>“The parallels between 2026 and the stagflationary 1970s are the most compelling in four decades,” Renaissance Macro Research wrote in late March. “Oil above $100, a Fed caught between mandates, sticky inflation, slowing growth, a weakening dollar, and a narrow market driven by overvalued technology — all echo the 1970s playbook.”</li>
            </ul>
            <p>Even after the S&amp;P 500 posted its best day of the year on Tuesday on speculation that the Trump administration could end the war with Iran, the blue chips were still down 5.1% in March, their worst monthly performance since the previous March as well as cementing the first quarter of 2026 as the worst for the S&amp;P 500 since Q3 2022.</p>
            <p>Meanwhile, the broad bond market also got battered last month. The Bloomberg US aggregate bond index — a broad gauge of the bond market — dropped roughly 2%, its worst month since October 2024.</p>
            <h1><span>THE TAKEAWAY</span></h1>
            <p>The characteristics of stocks that performed well over the last month also shifted, as quality companies with little debt and consistent profits gained favor. Such so-called value stocks are often thought to be better able to weather any potential downturn than companies with flakier fundamentals, which have soared on momentum and retail exuberance in recent months, but many momentum high-flyers had a brutal March.</p>
            <p>Interestingly, of the typical factors that investors spotlight, high-dividend shares were the best performers in March — falling only 3%. That likely reflects the fact that a lot of energy stocks are included in that category. But buying dividend-paying stocks that provide real income growth is also seen as an effective defense in a stagflationary environment.</p>
            <h1><a><strong>OpenAI is now valued at $852 billion</strong></a></h1>
            <p>2026 is set to be a massive year for IPOs, with SpaceX reportedly filing yesterday for what could be the biggest IPO of all time, and AI megastars Anthropic and OpenAI on deck after that. Not to be locked out of the superlative competition, OpenAI just closed out the biggest funding round in Silicon Valley history, raising a total of $122 billion for a staggering valuation that we had to put into perspective visually.</p>
            <p><a><strong>Worth how many Disneys?</strong></a></p>
            """,
        }

        stories = split_email_stories(email, email_subject="Quantum incoming")

        self.assertEqual(
            [story["title"] for story in stories],
            [
                "Google releases blockbuster white paper that spells quantum uncertainty for a whole lot of bitcoin",
                "Silver is in the spotlight. Here's a smarter way to explore it.",
                "The Iran war oil shock gave the markets ’70s stagflation vibes",
                "OpenAI is now valued at $852 billion",
            ],
        )
        self.assertTrue(stories[0]["text"].startswith("Google researchers sent a wake-up call Tuesday,"))
        self.assertTrue(stories[0]["text"].endswith("will exceed $16 trillion by 2030."))
        self.assertTrue(stories[1]["text"].startswith("Silver isn't just a store of value"))
        self.assertNotIn("Indexes are not directly investable.", stories[1]["text"])
        self.assertTrue(
            stories[2]["text"].endswith("an effective defense in a stagflationary environment.")
        )
        self.assertTrue(stories[3]["text"].startswith("2026 is set to be a massive year for IPOs"))
        self.assertTrue(stories[3]["text"].endswith("Worth how many Disneys?"))


if __name__ == "__main__":
    unittest.main()
