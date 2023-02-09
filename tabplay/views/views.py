#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tabplay/views/views.py
#
from flask import request, redirect, url_for, render_template
from flask import flash, session
from tabplay import app
from random import randint

from tabplay.views import genetic
from tabplay.views.genetic import Genome
from functools import partial

def fitness(genome: Genome, item_list, v_limit: float) -> float:
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

def greedy(item_list, v_limit):
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

@app.route('/', methods=['GET'])
def index():
	if session.get('items') == None:
		session['items'] = {}
	return render_template('index.html', items=session.get('items'))

@app.route('/', methods=['POST'])
def add_item():
	#global items
	items = session.get('items')
	fields = request.form
	new_id = randint(10000, 90000)
	while str(new_id) in items.keys():
		new_id = randint(10000, 90000)
	items[str(new_id)] = {'id': new_id, 'item': fields['item-name'], 
	'vol': float(fields['item-vol']), 'val': float(fields['item-val'])} 
	flash('Предмет \"{}\" добавлен'.format(fields['item-name']), 'good')
	session['items'] = items
	return redirect(url_for('index'))

@app.route('/packed', methods=['GET','POST'])
def pack():
	if request.method=='POST':
		items = session.get('items')
		if len(items)==0:
			flash("В списке нет ни одного предмета", "bad")
			return redirect(url_for('index'))
		fields = request.form
		v_limit = float(fields['total-vol'])
		item_list = [*items.values()]
		if min_vol(item_list)>v_limit:
			solution=[]
		else:
			population, generations = genetic.run_evolution(
				populate_func=partial(genetic.generate_population, size=20, genome_length=len(item_list)),
				fitness_func=partial(fitness, item_list=item_list, v_limit=v_limit),
				fitness_limit=tot_val(item_list),
				generation_limit=100
				#printer=genetic.print_stats
			)
			solution = items_from_genome(population[0], item_list)
		tv = tot_vol(solution)
		g_solution = greedy(item_list, v_limit)
		if tot_val(g_solution)>tot_val(solution) or tot_vol(solution)>v_limit:
			solution = g_solution
			flash(">--Жадное решение--<", "blue")
		else:
			flash('Рюкзак упакован', 'good')
		res={}
		res['limit']=v_limit
		res['names']=name_list(solution)
		res['vol']=tot_vol(solution)
		res['val']=tot_val(solution)
		session['res']=res
		return redirect(url_for('pack'))
	else:
		return render_template("results.html", res=session.get('res'))
	

	return render_template("results.html", res=session.get('res'))

@app.route('/api/data')
def data():
	items = session.get('items')
	return {'data': [*items.values()]}
	
@app.route('/api/data', methods=['POST'])
def update():
	items = session.get('items')
	data = request.get_json()
	print(data)
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
	print(items)
	return '', 204
	
@app.route('/api/delete', methods=['POST'])
def delete():
	#global items
	items = session.get('items')
	data = request.get_json()
	if 'id' not in data:
		abort(400)
	del items[str(data['id'])]
	session['items'] = items
	return '', 204
	
@app.route('/clear')
def clear():
	#global items
	items={}
	session['items']={}
	flash("Список очищен", "good")
	return redirect(url_for('index'))
	
@app.route('/load', methods=['POST'])
def read_file():
	#global items
	items = session.get('items')
	i_list = request.files['item-file']
	f_name = i_list.filename
	if f_name != '':
		file_ext = f_name.rsplit('.', 1)[1].lower()
		#print(file_ext)
		if file_ext not in app.config['UPLOAD_EXTENSIONS']:
			flash('Проверьте расширение файла', 'bad')
			return redirect(url_for('index'))
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
				new_id = randint(10000, 90000)
				while str(new_id) in items.keys():
					new_id = randint(10000, 90000)
				item['id'] = new_id
				items[str(new_id)] = item
				count += 1
			except Exception:
				pass
		flash("Файл прочитан, добавлено {} предметов".format(count), "good")
		session['items'] = items
		return redirect(url_for('index'))
		# except Exception:
			# flash("Неверный формат файла", "bad")
			# return redirect(url_for('index'))
	else:
		flash("Файл не выбран", "bad")
		return redirect(url_for('index'))
	return redirect(url_for('index'))
