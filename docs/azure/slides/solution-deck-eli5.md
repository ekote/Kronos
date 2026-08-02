# The deck, explained super simply 🧸

*A plain-words guide to `solution-deck.pdf`. No computer words. If you can picture
a weather app and a bouncing ball, you're ready.*

---

## What is this thing?

Imagine a **robot that watches prices go up and down** — like the price of a toy —
and tries to **guess what happens next**, the way a weather app guesses if it will
rain.

The robot is called **Kronos**. This deck is a little show that proves the robot
works, and shows how it lives on Microsoft's giant computers (called **Azure** and
**Fabric**) so it can watch prices *right now*, not yesterday.

---

## The picture we use: a bouncing price 🏀

Prices wiggle up and down all day, like a ball bouncing. Kronos looks at how the
ball has been bouncing and says *"I think it goes here next."*

- When the ball is bouncing in a normal way → Kronos guesses pretty well. ✅
- When something **crazy and surprising** happens (a loud BANG!) → nobody can guess
  that, not even the robot. 🙈
- The clever part: when the robot's guesses stop matching real life, it **raises its
  hand** and says *"Hey! Something changed, look at me!"* 🙋

That last part is the most important trick in the whole deck.

---

## Walking through the slides, one by one

**Slide 1 — "A model that forecasts. A system that acts."**
Meet the robot. It doesn't just guess — it can *do something* about the guess.

**Slide 2 — "Two planes. One loop."**
Think of a **factory line**. Prices come in one end 🍎, get tidied into neat boxes,
the robot makes a guess, and an alarm can ring at the other end 🔔. Two teams run
the line: one team (Fabric) moves the boxes, the other team (Azure ML) is the robot's
brain.

**Slide 3 — "Forecast in-regime — and know when it breaks."**
Three cards, three truths:
- It guesses the direction right about **2 out of 3 times**. 👍
- It **can't** guess the big surprise. (Nobody can — that's honest.) 🤷
- But it notices the surprise **super fast** and rings the alarm. ⏰

**Slide 4 — the big wiggly line (price & guess).**
The black line is what **really** happened. The dotted blue line is the robot's
**guess**. See how they match on the left? Then a **BANG** in the middle (the price
falls off a cliff), and the guess and reality split apart — the red patch is the
"oops" gap.

**Slide 5 — the "am I still right?" meter.**
This line shows **how wrong** the robot is. Normally it stays low and calm. When the
BANG happens, it shoots way up past the dotted line — and *that's* the robot raising
its hand. It figured it out in about **17 minutes**, all by itself.

**Slide 6 — the alarms (signals).**
When the robot feels sure a price will move a lot, it sends a little note 📩. The
table shows some notes and whether they came true. Most did.

**Slide 7 — "it fits in the big computers."**
Proof that everything the robot learned can be **saved into Microsoft Fabric** so
grown-ups can use it for real, with one little command.

**Slide 8 — the ending.**
The whole idea in one breath: **watch → guess → act**, over and over, forever, on a
tidy loop.

---

## The three things to remember 🌟

1. **It's a good guesser** when things are calm.
2. **It's honest** — it won't pretend to predict a surprise.
3. **It tells on itself** the moment its guesses go wrong, so people find out fast.

That third one is the real prize: a robot that **knows when it's confused** is much
safer than one that's confidently wrong.

---

## Two grown-up reminders (small print) 🔍

- The numbers in the deck come from a **pretend practice day** we made up (always the
  same, so the story is easy to retell). It shows the *machine works* — it is **not**
  a promise about real money.
- "Guessing prices" is never a sure thing. This is a tool to help careful people, with
  a safety alarm built in — not a magic money button. 🚫🪄
