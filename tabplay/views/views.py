#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tabplay/views/views.py
#

# TODO
# - store user data in db instead of session
# - clean db when session expires
# - add reading of genetic algo parameters from user
# - read config from environment (not cfg - this is for
# development only!) +/-DONE
# - add equipment and quota distribution problem solvers

from flask import request, redirect, url_for, render_template
from flask import flash, session
from tabplay import app
from random import randint, randrange, choice
import string

from tabplay.views import genetic
from tabplay.views.genetic import Genome, Inputs, EqGenome, EqPopulation
from tabplay.views.genetic import FitnessFunc
from typing import List, Optional, Callable, Tuple
from functools import partial
from math import log

#---------------------------------------------
# Functions for knapsack 0-1 problem
#---------------------------------------------

def fitness_knapsack(genome: Genome, item_list, v_limit: float) -> float:
    if len(genome) != len(item_list):
        raise ValueError("genome and things must be of same length")

    volume = 0
    value = 0
    for i, item in enumerate(item_list):
        if genome[i] == 1:
            volume += item['vol']
            value += item['val']

            if volume > v_limit:
                return 0

    return value

def items_from_genome(genome: Genome, item_list):
	result = []
	for i, item in enumerate(item_list):
		if genome[i] == 1:
			result += [item]
	return result

def name_list(item_list):
	return ', '.join(item['item'] for item in item_list)

def tot_vol(item_list):
	return round(sum([i['vol'] for i in item_list]), 1)
	
def tot_val(item_list):
	return round(sum([i['val'] for i in item_list]), 1)

def min_vol(item_list):
	volumes=[]
	for i in item_list:
		volumes.append(i['vol'])
	return min(volumes)

def ks_greedy(item_list, v_limit):
	new_list=sorted(item_list, key=lambda item: item['val']/(item['vol']+0.000001), reverse=True)
	final_list=[]
	available_space = v_limit
	for item in new_list:
		if item['vol'] <= available_space:
			final_list +=[item]
			#print('Put item {}'.format(item['item']))
			available_space = round(available_space-item['vol'],1)
			#print('Space left {}'.format(round(available_space,1)))
			if available_space <= 0:
				break
	return final_list

#---------------------------------------------
# Functions for equipment distribution problem
#---------------------------------------------

def eq_stats(things_list, people_list):
	#things_list=[*things.values()]
	#people_list=[*people.values()]
	w_list = [x['weight'] for x in things_list]
	b_list = [x['bias'] for x in people_list]
	c_list = [x['coeff'] for x in people_list]
	w_total = sum(w_list)+sum(b_list)
	c_total = sum(c_list)
	part = w_total / c_total
	norms = [x['coeff']*part-x['bias'] for x in people_list]
	return w_total, norms

def random_position(length: int) -> List[int]:
	l=[0]*length
	r=randrange(length)
	l[r]=1
	return l
    
def eq_sort_population(population: EqPopulation, fitness_func: FitnessFunc) -> EqPopulation:
	return sorted(population, key=fitness_func, reverse=False)
    
def eq_generate_genome(rows: int, cols: int) -> EqGenome:
	mx = []
	for i in range(rows):
		mx.append(random_position(cols))
	return mx
	
def eq_single_point_crossover(a: EqGenome, b: EqGenome) -> Tuple[EqGenome, EqGenome]:
	if eq_size_of_genome(a) != eq_size_of_genome(b):
		raise ValueError("Genomes a and b must be of the same size!")

	length = eq_size_of_genome(a)[0]
	if length < 2:
		return a, b
	p = randint(1, length - 1)
	return a[0:p] + b[p:], b[0:p] + a[p:]
    
def eq_size_of_genome(g: EqGenome) -> Tuple[int, int]:
	return len(g), len(g[0])

def eq_generate_population(size: int, genome_rows: int, genome_cols: int) -> EqPopulation:
	return [eq_generate_genome(genome_rows, genome_cols) for _ in range(size)]

def eq_mutation(genome: EqGenome, num: int = 1, probability: float = 0.5) -> Genome:
	for _ in range(num):
		index = randrange(len(genome))
		c = eq_size_of_genome(genome)[1]
		if random() > probability:
			genome[index] = random_position(c)
	return genome

def eq_population_fitness(population: EqPopulation, fitness_func: FitnessFunc) -> float:
	return sum([fitness_func(genome) for genome in population])
    
def eq_selection_pair(population: EqPopulation, fitness_func: FitnessFunc) -> EqPopulation:
	return choices(
		population = population,
		weights=[fitness_func(gene) for gene in population],
		k=2
	)

def fitness_eq (genome: EqGenome, weights: Inputs, norms: Inputs, importance: Inputs) -> float:
	rows, cols = eq_size_of_genome(genome)
	if rows!=len(weights) or cols!=len(norms) or cols!=len(importance):
		print('Other inputs length must match Genome size!')
		return -1
	else:
		f = 0
		for j in range(cols):
			w = 0
			for i in range(rows):
				w += genome[i][j]*weights[i]
			f = f + importance[j]*abs(w-norms[j])
		return f

def eq_find_scores(things_list, people_list, matrix):
	delta = []
	#things_list = [*things.values()]
	#people_list = [*people.values()]
	#print(things_list)
	w_list = [x['weight'] for x in things_list]
	b_list = [x['bias'] for x in people_list]
	c_list = [x['coeff'] for x in people_list]
	i_list = [x['importance'] for x in people_list]
	w_tot, n_list = eq_stats(things_list, people_list)
	for j in range(len(matrix[0])):
		w = 0 
		for i in range(len(matrix)):
			w = w + matrix[i][j]*w_list[i]
		delta.append((w-n_list[j])*i_list[j])
	return delta

def eq_list_distribution(things_list, people_list, norms: Inputs, matrix: EqGenome, delta: Inputs):
	#things_list = [*things.values()]
	#people_list = [*people.values()]
	final_list = []
	for j in range(len(people_list)):
		person_list = []
		for i in range(len(things_list)):
			if matrix[i][j] != 0:
				person_list.append(things_list[i]['thing'])
		final_list.append((people_list[j]['name'], person_list, 
						delta[j]/people_list[j]['importance'], 
						norms[j]+people_list[j]['bias'], people_list[j]['bias']))
	return final_list

def eq_generate_report(list_distr, score, w_tot):
	#generate html-table style report for equipment distribution problem
	html ='<p>\
			<strong>Общий вес снаряжения: {0}</strong><br>\
			<strong>Целевая функция распределения: {1:.1f}</strong><br>\
		</p>\
        <table class="res-table">\
			<tr>\
				<th>Участник</th>\
				<th>Список снаряжения</th>\
				<th>Норма веса</th>\
				<th>Начальный вес</th>\
				<th>Перевес/недовес</th>\
			</tr>'.format(w_tot, score)
	for person in list_distr:
		t_list = ', '.join(x for x in person[1])
		if person[2] >= 0:
			q = 'перевес'
		else:
			q = 'недовес'
		html += '<tr>\
		<td>{0}</td><td>{1}</td><td>{2:.1f}</td><td>{3}</td><td>{4} {5:.1f}</td>\
		</tr>'.format(person[0], t_list, person[3], person[4], q, abs(person[2]))
	html +='</table>'
	return html

def eq_greedy(things_list, people_list):
	#greedy solution for equipment distribution problem
	matrix=[]
	for _ in range(len(things_list)):
		l=[0]*len(people_list)
		matrix.append(l)
	for i in range(len(things_list)):
		local = eq_find_scores(things_list, people_list, matrix)
		s_loc = sorted(local)
		index = local.index(s_loc[0])
		matrix[i][index]=1
	return matrix

def random_string(length):
	#Generate random alphanumeric string with length=length
	letters = string.ascii_letters
	digits = string.digits
	symbols = letters + digits
	return ''.join(choice(symbols) for i in range (length))

#----------------------------------------
#Functions for quota distribution problem
#----------------------------------------

def quotas_find_scores(customers_list, matrix):
	delta = []
	o_list = [x['order'] for x in customers_list]
	p_list = [abs(log(x['priority'])+1) for x in customers_list]
	for j in range(len(matrix[0])):
		w = 0 
		for i in range(len(matrix)):
			w = w + matrix[i][j]
		delta.append((w-o_list[j])*p_list[j])
	return delta
	
def quotas_greedy(qlimit, customers_list):
	#greedy solution for equipment distribution problem
	matrix=[]
	for _ in range(qlimit):
		l=[0]*len(customers_list)
		matrix.append(l)
	for i in range(qlimit):
		local = quotas_find_scores(customers_list, matrix)
		s_loc = sorted(local)
		index = local.index(s_loc[0])
		print('Give quota to {0}, underscore: {1}'.format(customers_list[index]['customer'],
		s_loc[0]))
		matrix[i][index]=1
	return matrix

def quotas_generate_report(qlimit, residue, winner_score, customers_list, matrix):
	numbers=[]
	n=0
	for j in range(len(matrix[0])):
		for i in range(len(matrix)):
			n = n + matrix[i][j]
		numbers.append(n)
		n=0
	html = '<p>\
			<strong>Объем квот: {0}</strong><br>\
			<strong>Целевая функция распределения: {1:.1f}</strong><br>'.format(qlimit+residue, 
			winner_score)
	if residue>0:
		html += '<strong>Неиспользовано квот: {0}</strong>'.format(residue)
	html +='</p>\
        <table class="res-table">\
			<tr>\
				<th>Заказчик</th>\
				<th>Приоритет</th>\
				<th>Объем заказа</th>\
				<th>Выдано квот</th>\
				<th>Недополучено квот</th>\
			</tr>'.format(qlimit, winner_score)
	for i in range(len(customers_list)):
		html += '<tr>\
		<td>{0}</td><td>{1:.0f}</td><td>{2:.0f}</td><td>{3:.0f}</td><td>{4:.0f}</td>\
		</tr>'.format(customers_list[i]['customer'], customers_list[i]['priority'], 
		customers_list[i]['order'], numbers[i], customers_list[i]['order']-numbers[i])
	html +='</table>'
	return html

#==============================
# View entries
#==============================

@app.route('/', methods=['GET'])
def index():
	if session.get('last_page') == None:
		session['last_page'] = 'index'
		print('index')
	return render_template('index.html')

#----------------------------
#Knapsack 0-1 problem
#----------------------------

@app.route('/knapsack/main')
def knapsack_main():
	last = session.get('last_page')
	if last == None or not last == 'knapsack':
		print(last)
		session['items'] = {}
		session['last_page'] = 'knapsack'
	else:
		print('knapsack')
	return render_template('knapsack_index.html', items=session.get('items'))

@app.route('/knapsack/main', methods=['POST'])
def ks_add_item():
	items = session.get('items')
	fields = request.form
	new_id = random_string(8)
	while new_id in items.keys():
		new_id = random_string(8)
	items[new_id] = {'id': new_id, 'item': fields['item-name'], 
	'vol': float(fields['item-vol']), 'val': float(fields['item-val'])} 
	flash('Предмет \"{}\" добавлен'.format(fields['item-name']), 'good')
	session['items'] = items
	#print(items)
	return redirect(url_for('knapsack_main'))

@app.route('/knapsack/packed', methods=['GET','POST'])
def ks_pack():
	if request.method=='POST':
		items = session.get('items')
		if len(items)==0:
			flash("В списке нет ни одного предмета", "bad")
			return redirect(url_for('knapsack_main'))
		fields = request.form
		v_limit = float(fields['total-vol'])
		item_list = [*items.values()]
		if min_vol(item_list)>v_limit:
			solution=[]
		else:
			population, generations = genetic.run_evolution(
				populate_func=partial(genetic.generate_population, size=20, genome_length=len(item_list)),
				fitness_func=partial(fitness_knapsack, item_list=item_list, v_limit=v_limit),
				fitness_limit=tot_val(item_list),
				generation_limit=100
				#printer=genetic.print_stats
			)
			solution = items_from_genome(population[0], item_list)
		tv = tot_vol(solution)
		g_solution = ks_greedy(item_list, v_limit)
		if tot_val(g_solution)>tot_val(solution) or tot_vol(solution)>v_limit:
			solution = g_solution
			flash(">--Жадное решение--<", "blue")
		else:
			flash('Рюкзак упакован', 'good')
		solution = sorted(solution, key=lambda item: item['val'], reverse=True)
		res={}
		res['limit']=v_limit
		res['names']=name_list(solution)
		res['vol']=tot_vol(solution)
		res['val']=tot_val(solution)
		session['res']=res
		return redirect(url_for('ks_pack'))
	else:
		return render_template("ks_results.html", res=session.get('res'))
	

	return render_template("ks_results.html", res=session.get('res'))

@app.route('/knapsack/api/data')
def ks_data():
	items = session.get('items')
	return {'data': [*items.values()]}
	
@app.route('/knapsack/api/data', methods=['POST'])
def ks_update():
	items = session.get('items')
	data = request.get_json()
	#print(data)
	if 'id' not in data:
		abort(400)
	item = items[data['id']]
	for field in ['item', 'vol', 'val']:
		if field in data:
			if field=='vol' or field=='val':
				try:
					item[field] = round(float(data[field]),1)
				except Exception:
					pass
			else:
				item[field] = data[field]
	session['items'] = items
	#print(items)
	return '', 204
	
@app.route('/knapsack/api/delete', methods=['POST'])
def ks_delete():
	#global items
	items = session.get('items')
	data = request.get_json()
	if 'id' not in data:
		abort(400)
	del items[str(data['id'])]
	session['items'] = items
	return '', 204
	
@app.route('/knapsack/clear')
def ks_clear():
	#global items
	items={}
	session['items']={}
	flash("Список очищен", "good")
	return redirect(url_for('knapsack_main'))
	
@app.route('/knapsack/load', methods=['POST'])
def ks_read_file():
	#global items
	items = session.get('items')
	i_list = request.files['item-file']
	f_name = i_list.filename
	if f_name != '':
		file_ext = f_name.rsplit('.', 1)[1].lower()
		#print(file_ext)
		if file_ext not in app.config['UPLOAD_EXTENSIONS']:
			flash('Проверьте расширение файла', 'bad')
			return redirect(url_for('knapsack_main'))
		lines=list(i_list)
		count = 0
		for l in lines:
			data=l.decode('utf-8').rstrip('\n').split(',')
			#print(data)
			item={}
			try:
				item['item'] = data[0]
				item['vol'] = round(float(data[1]),1)
				item['val'] = round(float(data[2]),1)
				new_id = random_string(8)
				while new_id in items.keys():
					new_id = random_string(8)
				item['id'] = new_id
				items[new_id] = item
				count += 1
			except Exception:
				pass
		flash("Файл прочитан, добавлено {} предметов".format(count), "good")
		session['items'] = items
		return redirect(url_for('knapsack_main'))
		# except Exception:
			# flash("Неверный формат файла", "bad")
			# return redirect(url_for('index'))
	else:
		flash("Файл не выбран", "bad")
		return redirect(url_for('knapsack_main'))
	return redirect(url_for('knapsack_main'))

@app.route('/about')
def about():
	return render_template("about.html")

#------------------------------
#Equipment distribution problem
#------------------------------
# We store things dict in session.things variable
# and people dict in session.people variable

@app.route('/equip/main')
def equip_main():
	last = session.get('last_page')
	if last == None or not last == 'equip':
		print(last)
		session['things'] = {}
		session['people'] = {}
		session['last_page'] = 'equip'
	else:
		print('equip')
	return render_template('equip_index.html', data={'things': session.get('things'),
	'people': session.get('people')})

#------------------------
# things table functions
#------------------------

@app.route('/equip/add_thing', methods=['POST'])
def eq_t_add():
	things = session.get('things')
	fields = request.form
	new_id = random_string(8)
	while new_id in things.keys():
		new_id = random_string(8)
	things[new_id] = {'id': new_id, 'thing': fields['thing-name'], 
		'weight': float(fields['thing-weight'])} 
	flash('Предмет \"{}\" добавлен'.format(fields['thing-name']), 'good')
	session['things'] = things
	#print(things)
	return redirect(url_for('equip_main'))

@app.route('/equip/api/del_thing', methods=['POST'])
def eq_t_del():
	things = session.get('things')
	data = request.get_json()
	if 'id' not in data:
		abort(400)
	del things[str(data['id'])]
	session['things'] = things
	return '', 204

@app.route('/equip/api/things_data')
def eq_things():
	things = session.get('things')
	return {'data': [*things.values()]}
	
@app.route('/equip/api/things_data', methods=['POST'])
def eq_t_update():
	things = session.get('things')
	data = request.get_json()
	#print(data)
	if 'id' not in data:
		abort(400)
	thing = things[data['id']]
	for field in ['thing', 'weight']:
		if field in data:
			if field=='weight':
				try:
					thing[field] = round(float(data[field]),1)
				except Exception:
					pass
			else:
				thing[field] = data[field]
	session['things'] = things
	#print(things)
	return '', 204
	
@app.route('/equip/load_things', methods=['POST'])
def eq_t_read():
	things = session.get('things')
	i_list = request.files['things-file']
	f_name = i_list.filename
	if f_name != '':
		file_ext = f_name.rsplit('.', 1)[1].lower()
		#print(file_ext)
		if file_ext not in app.config['UPLOAD_EXTENSIONS']:
			flash('Проверьте расширение файла', 'bad')
			return redirect(url_for('equip_main'))
		lines=list(i_list)
		count = 0
		for l in lines:
			data=l.decode('utf-8').rstrip('\n').split(',')
			#print(data)
			thing={}
			try:
				thing['thing'] = data[0]
				thing['weight'] = round(float(data[1]),1)
				new_id = random_string(8)
				while new_id in things.keys():
					new_id = random_string(8)
				thing['id'] = new_id
				things[new_id] = thing
				count += 1
			except Exception:
				pass
		flash("Файл прочитан, добавлено {} предметов".format(count), "good")
		session['things'] = things
		return redirect(url_for('equip_main'))
	else:
		flash("Файл не выбран", "bad")
		return redirect(url_for('equip_main'))
	return redirect(url_for('equip_main'))
	
@app.route('/equip/clear_things')
def eq_t_clear():
	session['things']={}
	flash("Список снаряжения очищен", "good")
	return redirect(url_for('equip_main'))
	return
	
#----------------------
#people table functions
#----------------------

@app.route('/equip/add_people', methods=['POST'])
def eq_p_add():
	people = session.get('people')
	fields = request.form
	new_id = random_string(8)
	while new_id in people.keys():
		new_id = random_string(8)
	people[new_id] = {'id': new_id, 'name': fields['person-name'], 
		'coeff': float(fields['person-coeff']), 'bias': float(fields['person-bias']),
		'importance': float(fields['person-importance'])} 
	flash('Участник \"{}\" добавлен'.format(fields['person-name']), 'good')
	session['people'] = people
	#print(people)
	return redirect(url_for('equip_main'))

@app.route('/equip/api/del_person', methods=['POST'])
def eq_p_del():
	people = session.get('people')
	data = request.get_json()
	if 'id' not in data:
		abort(400)
	del people[str(data['id'])]
	session['people'] = people
	return '', 204

@app.route('/equip/api/people_data')
def eq_people():
	people = session.get('people')
	return {'data': [*people.values()]}
	
@app.route('/equip/api/people_data', methods=['POST'])
def eq_p_update():
	people = session.get('people')
	data = request.get_json()
	#print(data)
	if 'id' not in data:
		abort(400)
	person = people[data['id']]
	for field in ['name', 'coeff', 'bias', 'importance']:
		if field in data:
			if field=='coeff' or field=='bias' or field=='importance':
				try:
					person[field] = round(float(data[field]),1)
				except Exception:
					pass
			else:
				person[field] = data[field]
	session['people'] = people
	#print(people)
	return '', 204
	
@app.route('/equip/load_people', methods=['POST'])
def eq_p_read():
	people = session.get('people')
	i_list = request.files['people-file']
	f_name = i_list.filename
	if f_name != '':
		file_ext = f_name.rsplit('.', 1)[1].lower()
		#print(file_ext)
		if file_ext not in app.config['UPLOAD_EXTENSIONS']:
			flash('Проверьте расширение файла', 'bad')
			return redirect(url_for('equip_main'))
		lines=list(i_list)
		count = 0
		for l in lines:
			data=l.decode('utf-8').rstrip('\n').split(',')
			#print(data)
			person={}
			try:
				person['name'] = data[0]
				person['coeff'] = round(float(data[1]),1)
				person['bias'] = round(float(data[2]),1)
				person['importance'] = round(float(data[3]),1)
				new_id = random_string(8)
				while new_id in people.keys():
					new_id = random_string(8)
				person['id'] = new_id
				people[new_id] = person
				count += 1
			except Exception:
				pass
		flash("Файл прочитан, добавлено {} участников".format(count), "good")
		session['people'] = people
		return redirect(url_for('equip_main'))
	else:
		flash("Файл не выбран", "bad")
		return redirect(url_for('equip_main'))
	return redirect(url_for('equip_main'))
	
@app.route('/equip/clear_people')
def eq_p_clear():
	session['people']={}
	flash("Список участников очищен", "good")
	return redirect(url_for('equip_main'))

@app.route('/equip/pack', methods=['GET','POST'])
def eq_pack():
	if request.method =='POST':
		things = session['things']
		people = session['people']
		if len(things)==0:
			flash("Список снаряжения пуст", "bad")
			return redirect(url_for('equip_main'))
		if len(people)==0:
			flash("Список участников пуст", "bad")
			return redirect(url_for('equip_main'))
		
		things_list = [*things.values()]
		things_list = sorted(things_list, key=lambda thing: thing['weight'], reverse=True )
		people_list = [*people.values()]
		w_list = [x['weight'] for x in things_list]
		b_list = [x['bias'] for x in people_list]
		c_list = [x['coeff'] for x in people_list]
		i_list = [x['importance'] for x in people_list]
		total_w, n_list = eq_stats(things_list, people_list)
		
		winner = eq_greedy(things_list, people_list)
		winner_score = fitness_eq(winner, w_list, n_list, i_list)
		
		rows = len(things_list)
		cols = len(people_list)
		pop_size = 20
		
		population, generations = genetic.run_evolution(
		populate_func = partial(eq_generate_population, size=pop_size, genome_rows = rows, 
						genome_cols = cols),
		fitness_func = partial(fitness_eq, weights = w_list, 
						norms = n_list, importance = i_list),
		mutation_func = partial(eq_mutation, num = 4, probability = 0.5),
		fitness_limit = winner_score/2, generation_limit=pop_size*rows*cols)
		score = fitness_eq(population[0], w_list, n_list, i_list)
		
		if winner_score >= score:
			winner = population[0]
			winner_score = score
			flash("Снаряжение распределено", "good")
		else:
			flash('>--Жадное решение--<', "blue")
		delta = eq_find_scores(things_list, people_list, winner)
		d_list = eq_list_distribution(things_list, people_list, n_list, winner, delta)
		html_report = eq_generate_report(d_list, winner_score, total_w)
		session['report']=html_report
		return redirect(url_for("eq_pack"))
	else:
		return render_template("equip_index.html", report = session.get('report'))

#-----------------------------
# Quotas distribution functions
#-----------------------------

@app.route('/quotas/main')
def quotas_main():
	last = session.get('last_page')
	if last == None or not last == 'quotas':
		print(last)
		session['quotas'] = {}
		session['customers'] = {}
		session['last_page'] = 'quotas'
	else:
		print('quotas')
	return render_template('quotas_index.html', data={'quotas': session.get('quotas'),
	'people': session.get('people')})

@app.route('/quotas/add', methods=['POST'])
def quotas_add():
	customers = session.get('customers')
	fields = request.form
	new_id = random_string(8)
	while new_id in customers.keys():
		new_id = random_string(8)
	customers[new_id] = {'id': new_id, 'customer': fields['customer'], 
		'order': abs(int(fields['order'])), 'priority': abs(int(fields['priority']))} 
	flash('Заказчик \"{}\" добавлен'.format(fields['customer']), 'good')
	session['customers'] = customers
	#print(people)
	return redirect(url_for('quotas_main'))
	
@app.route('/quotas/read', methods=['POST'])
def quotas_read():
	customers = session.get('customers')
	i_list = request.files['customers-file']
	f_name = i_list.filename
	if f_name != '':
		file_ext = f_name.rsplit('.', 1)[1].lower()
		#print(file_ext)
		if file_ext not in app.config['UPLOAD_EXTENSIONS']:
			flash('Проверьте расширение файла', 'bad')
			return redirect(url_for('equip_main'))
		lines=list(i_list)
		count = 0
		for l in lines:
			data=l.decode('utf-8').rstrip('\n').split(',')
			#print(data)
			customer={}
			try:
				customer['customer'] = data[0]
				customer['order'] = abs(round(int(data[1]),0))
				customer['priority'] = abs(round(int(data[2]),0))
				new_id = random_string(8)
				while new_id in customers.keys():
					new_id = random_string(8)
				customer['id'] = new_id
				customers[new_id] = customer
				count += 1
			except Exception:
				pass
		flash("Файл прочитан, добавлено {} заказчиков".format(count), "good")
		session['customers'] = customers
		return redirect(url_for('quotas_main'))
	else:
		flash("Файл не выбран", "bad")
		return redirect(url_for('quotas_main'))
	return redirect(url_for('quotas_main'))
	
@app.route('/quotas/clear')
def quotas_clear():
	session['customers']={}
	flash("Список заказчиков очищен", "good")
	return redirect(url_for('quotas_main'))

@app.route('/quotas/api/del_customer', methods=['POST'])
def quotas_del():
	customers = session.get('customers')
	data = request.get_json()
	if 'id' not in data:
		abort(400)
	del customers[str(data['id'])]
	session['customers'] = customers
	return '', 204

@app.route('/quotas/api/customers_data')
def quotas_data():
	customers = session.get('customers')
	return {'data': [*customers.values()]}
	
@app.route('/quotas/api/customers_data', methods=['POST'])
def quotas_update():
	customers = session.get('customers')
	data = request.get_json()
	#print(data)
	if 'id' not in data:
		abort(400)
	customer = customers[data['id']]
	for field in ['customer', 'order', 'priority']:
		if field in data:
			if field=='order' or field=='priority':
				try:
					customer[field] = abs(round(int(data[field]),0))
				except Exception:
					pass
			else:
				customer[field] = data[field]
	session['customers'] = customers
	#print(items)
	return '', 204

@app.route('/quotas/arrange', methods=['GET','POST'])
def quotas_arrange():
	if request.method =='POST':
		customers = session['customers']
		if len(customers)==0:
			flash("Список заказчиков пуст", "bad")
			return redirect(url_for('quotas_main'))
		customers_list=[*customers.values()]
		customers_list=sorted(customers_list, key=lambda x: x['priority'],
		reverse=True)
		fields = request.form
		qlimit = int(fields['qlimit'])
		residue = 0
		p_list = [abs(log(x['priority'])+1) for x in customers_list]
		o_list = [x['order'] for x in customers_list]
		if sum(o_list) < qlimit:
			residue = int(qlimit - sum(o_list))
			qlimit = int(qlimit - residue)
		w_list = [1]*qlimit
		winner = quotas_greedy(qlimit, customers_list)
		winner_score = fitness_eq(winner, w_list, o_list, p_list)
		print ('greedy {}'.format(winner_score))
		rows = qlimit
		cols = len(customers_list)
		pop_size = 20
		
		population, generations = genetic.run_evolution(
		populate_func = partial(eq_generate_population, size=pop_size, genome_rows = rows, 
						genome_cols = cols),
		fitness_func = partial(fitness_eq, weights = w_list, 
						norms = o_list, importance = p_list),
		mutation_func = partial(eq_mutation, num = 4, probability = 0.5),
		fitness_limit = winner_score/2, generation_limit=pop_size*rows*cols)
		score = fitness_eq(population[0], w_list, o_list, p_list)
		
		if winner_score >= score:
			winner = population[0]
			winner_score = score
			flash("Квоты распределены", "good")
		else:
			flash('>--Жадное решение--<', "blue")
		#delta = quotas_find_scores(qlimit, customers_list, winner)
		html_report = quotas_generate_report(qlimit, residue, winner_score, customers_list, winner)
		session['report'] = html_report
		return redirect(url_for("quotas_arrange"))
	else:
		return render_template("quotas_index.html", report = session.get('report'))
	return redirect(url_for('quotas_main'))
