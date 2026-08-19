# ITCH Films Premium - Project Vision

## Main Goal

Build a premium movie catalog web application that exceeds typical educational Flask projects.

The project must look like a real commercial product.

---

## Project Rules

These rules are mandatory.

Do not ignore them.

Do not replace them without user approval.

If a new request conflicts with this document, ask for confirmation before changing the project direction.

---

## Development Process

Always follow this order:

1. Explain the plan.
2. Show affected files.
3. Wait for confirmation when changes are large.
4. Implement only approved changes.
5. Explain what was changed.
6. Wait for next instruction.

Never rewrite the whole project without permission.

Never delete files without permission.

Never change architecture without permission.

---

## Technology Stack

Backend:

* Python
* Flask
* MySQL (Sakila)
* MongoDB

Frontend:

* Bootstrap 5
* Custom CSS
* JavaScript

---

## Course Requirements

Must implement:

* Search by movie title
* Search by genre
* Search by year range
* Maximum 10 results per page
* Log every search request into MongoDB
* Statistics page
* Popular searches
* Recent searches

These requirements are mandatory.

---

## Design Vision

Style inspiration:

* Netflix
* Apple TV+
* Disney+
* IMDB Pro

Do not copy them.

Create a unique design.

Requirements:

* Dark Theme
* Glassmorphism
* Smooth Animations
* Premium UI
* Large movie cards
* Responsive design
* Mobile Friendly
* Modern Typography
* Cinematic atmosphere

---

## Image System

Sakila does not contain movie posters.

Use:

movie_images.py

or

static/data/movie_images.json

All image links must be stored there.

Never hardcode image URLs inside HTML.

Preferred image sources:

1. Unsplash
2. Pexels
3. Pixabay

Only use free high-quality images.

Hero banners:

* 2400px+

Movie cards:

* 1600px+

If a movie has no image:

* Use genre image.

---

## MongoDB Rules

Store every search request.

Collection fields:

* timestamp
* search_type
* search_value
* genre
* year_from
* year_to
* results_count

Statistics page must display:

* 5 most popular searches
* 5 latest searches

---

## Code Quality Rules

Code must be:

* Beginner friendly
* Well commented
* PEP8 compliant
* Easy to explain during project defense

Every function must have a clear purpose.

Avoid unnecessary complexity.

Prefer readability over optimization.

---

## Teaching Mode

Always explain:

* why the file exists
* why the function exists
* how the code works

Assume the developer is learning Python Backend Development.

Do not skip explanations.

---

## Memory Rules

Treat this file as the permanent project vision.

When the user adds new project requirements:

* summarize them
* confirm them
* update architecture if necessary

Do not forget previously approved project requirements.

Always check this document before proposing new architecture or code.
